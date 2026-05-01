# 漫剧 Agent 深度优化设计

> 设计时间：2026 年 5 月  
> 设计依据：`漫剧agent深度分析.md`、`主流agent知识体系.md`、当前 ttsapp frontend/backend 漫剧 Agent 实现。  
> 目标：把当前“ReAct + 工具 + 前端展示型计划”的漫剧 Agent，升级为“TaskGraph + ReAct Step Executor + ArtifactMemory + CompletionAuditor + Replanner”的工程化创作 Agent。

---

## 0. 设计总纲

### 0.1 当前核心问题

当前漫剧 Agent 最大问题不是工具不够，而是缺少系统侧的权威任务状态。

现状可以概括为：

```text
用户目标
  ↓
LLM 自己在 messages 中记住计划
  ↓
LLM 返回 tool_call
  ↓
后端执行工具
  ↓
工具结果写回 messages
  ↓
LLM 自己判断是否继续
  ↓
前端根据事件和文本猜测任务状态
```

这个结构能完成简单任务，但复杂任务容易出现：

- 模型列了 TODO 但没有调用工具。
- 工具失败后模型仍然总结为完成。
- 前端显示的计划与后端真实执行不一致。
- 产物只作为 URL 字符串存在，无法绑定到具体步骤。
- `done` 只代表流结束，不一定代表业务完成。
- “继续执行”时系统不知道应该继续哪一步。

### 0.2 优化后的目标形态

目标结构：

```text
用户目标
  ↓
IntentClassifier：识别任务类型和能力需求
  ↓
TaskPlanner：生成结构化 TaskGraph
  ↓
TaskGraphStore：持久化任务、步骤、产物、错误
  ↓
ReActStepExecutor：围绕当前 step 调用 LLM 和工具
  ↓
ToolExecutor：执行工具并返回统一 ToolResult
  ↓
Observer：校验工具结果和产物可用性
  ↓
CompletionAuditor：根据 TaskGraph 判断是否完成
  ↓
Replanner：失败/阻塞/缺工具时重规划
  ↓
Reporter：输出后端权威 FinalReport
```

核心升级：

```text
从“LLM 自己记住下一步”
升级为
“系统显式知道下一步”
```

### 0.3 设计原则

- **后端状态权威**：任务是否完成以 `AgentTask/AgentStep/AgentArtifact` 为准，不以前端 computed 或模型文本为准。
- **前端只展示状态**：前端不再自行推断最终完成度，只消费后端事件和最终报告。
- **工具结果强类型化**：所有工具必须返回统一 `ToolResult`。
- **一步一验收**：每个 step 执行完成后必须由 Observer/Auditor 判定是否成功。
- **失败可恢复**：失败不是直接结束，而是进入 retry/fallback/replan/ask_user/block。
- **ReAct 不废弃，而是收编**：保留 ReAct 灵活性，但让它在 step 范围内工作。
- **DAG 优先于线性计划**：图片转视频、TTS、合成等任务应显式表达依赖和并行关系。

---

## 1. 目标架构设计

### 1.1 总体模块图

```text
ComicAgent vNext
│
├── API Layer
│   ├── WebSocket: /api/v1/comic-agent/ws/chat
│   ├── Task Query API
│   ├── Artifact Query API
│   └── Approval API
│
├── Agent Runtime
│   ├── IntentClassifier
│   ├── TaskPlanner
│   ├── TaskGraphStore
│   ├── TaskScheduler
│   ├── ReActStepExecutor
│   ├── CompletionAuditor
│   ├── Replanner
│   └── Reporter
│
├── Tool Layer
│   ├── ToolRegistry DB
│   ├── ToolDefinitionBuilder
│   ├── ToolExecutor
│   ├── ToolResultNormalizer
│   └── ToolRiskPolicy
│
├── Memory Layer
│   ├── ConversationMemory
│   ├── ArtifactMemory
│   ├── StepMemory
│   └── CompactHistory
│
├── Event Layer
│   ├── task_created
│   ├── task_update
│   ├── step_update
│   ├── tool_start
│   ├── tool_done
│   ├── artifact_created
│   ├── approval_required
│   ├── incomplete
│   ├── blocked
│   ├── failed
│   └── done
│
└── Frontend Workbench
    ├── Task Overview
    ├── Step DAG/Timeline
    ├── Artifact Gallery
    ├── Execution Log
    ├── Approval Panel
    └── Final Report
```

### 1.2 核心运行流程

```text
1. 用户发送消息
2. 后端创建 AgentTask
3. IntentClassifier 输出 task_type / capabilities
4. TaskPlanner 生成 AgentStep DAG
5. 保存 TaskGraph
6. 前端收到 task_created + step_update
7. TaskScheduler 找到 ready step
8. ReActStepExecutor 执行当前 step
9. ToolExecutor 返回 ToolResult
10. Observer 校验产物
11. 更新 AgentStep + AgentArtifact
12. CompletionAuditor 判断全局状态
13. 如果未完成：继续调度 ready step
14. 如果失败：进入 Replanner
15. 如果阻塞：发 blocked/incomplete
16. 如果全部完成：Reporter 生成 final_report，发 done completed
```

### 1.3 ReAct 在新架构中的位置

当前 ReAct 是全局自由循环：

```text
用户目标 → LLM 自由决定每一步工具
```

优化后 ReAct 变成 step 级执行器：

```text
当前 step + 可用输入 + 可用工具 → LLM 选择本 step 的 tool_call
```

也就是说：

```text
TaskGraph 控制“应该做什么”
ReAct 控制“这一步具体怎么调用工具”
ToolExecutor 控制“实际执行”
Auditor 控制“是否完成”
```

这样既保留 LLM 灵活性，又避免它忘记任务目标。

---

## 2. 数据库模型设计

### 2.1 agent_tasks

用途：记录一次用户目标级任务。

字段建议：

```sql
CREATE TABLE agent_tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_uid VARCHAR(64) NOT NULL UNIQUE,
    conversation_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    user_goal TEXT NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_step_uid VARCHAR(64),
    model_id VARCHAR(128),
    auto_mode BOOLEAN DEFAULT FALSE,
    final_report JSON,
    error JSON,
    metadata JSON,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    finished_at DATETIME
);
```

状态枚举：

```text
created
planning
running
awaiting_approval
incomplete
blocked
failed
canceled
completed
```

### 2.2 agent_steps

用途：记录任务拆解后的每个执行步骤。

```sql
CREATE TABLE agent_steps (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    step_uid VARCHAR(64) NOT NULL UNIQUE,
    task_uid VARCHAR(64) NOT NULL,
    parent_step_uid VARCHAR(64),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    step_type VARCHAR(64) NOT NULL,
    tool_name VARCHAR(128),
    status VARCHAR(32) NOT NULL,
    depends_on JSON,
    inputs JSON,
    outputs JSON,
    error JSON,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 1,
    sort_order INT DEFAULT 0,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    started_at DATETIME,
    finished_at DATETIME
);
```

状态枚举：

```text
pending
ready
running
awaiting_approval
succeeded
failed
blocked
skipped
canceled
```

步骤类型：

```text
plan
llm
tool
condition
parallel_group
merge
report
```

### 2.3 agent_artifacts

用途：把图片、视频、音频、文件绑定到任务和步骤。

```sql
CREATE TABLE agent_artifacts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    artifact_uid VARCHAR(64) NOT NULL UNIQUE,
    task_uid VARCHAR(64) NOT NULL,
    step_uid VARCHAR(64),
    artifact_type VARCHAR(32) NOT NULL,
    title VARCHAR(255),
    url TEXT NOT NULL,
    file_path TEXT,
    mime_type VARCHAR(128),
    size_bytes BIGINT,
    verified BOOLEAN DEFAULT FALSE,
    metadata JSON,
    created_at DATETIME NOT NULL
);
```

产物类型：

```text
image
video
audio
text
file
json
```

### 2.4 agent_events

用途：持久化事件流，支持断线恢复和回放。

```sql
CREATE TABLE agent_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_uid VARCHAR(64) NOT NULL UNIQUE,
    task_uid VARCHAR(64),
    step_uid VARCHAR(64),
    event_type VARCHAR(64) NOT NULL,
    payload JSON NOT NULL,
    created_at DATETIME NOT NULL
);
```

### 2.5 tool_invocations

用途：记录每一次工具调用。

```sql
CREATE TABLE tool_invocations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    invocation_uid VARCHAR(64) NOT NULL UNIQUE,
    task_uid VARCHAR(64) NOT NULL,
    step_uid VARCHAR(64),
    tool_call_id VARCHAR(128),
    tool_name VARCHAR(128) NOT NULL,
    input JSON,
    output JSON,
    status VARCHAR(32) NOT NULL,
    error JSON,
    started_at DATETIME,
    finished_at DATETIME,
    created_at DATETIME NOT NULL
);
```

---

## 3. 统一 ToolResult 设计

### 3.1 当前问题

当前工具返回格式不统一，前端和 Agent 需要猜测：

```text
status/success/ok/error
image_url/video_url/audio_url/file_path
字符串 JSON / dict 混合
错误文本不统一
```

### 3.2 标准 ToolResult

所有工具统一返回：

```json
{
  "status": "success",
  "tool": "generate_image",
  "tool_call_id": "call_xxx",
  "artifacts": [
    {
      "type": "image",
      "url": "/uploads/agent_outputs/xxx.png",
      "file_path": "backend/uploads/agent_outputs/xxx.png",
      "mime_type": "image/png",
      "metadata": {
        "width": 1024,
        "height": 1024,
        "provider": "comfyui"
      }
    }
  ],
  "data": {},
  "error": null,
  "retryable": false,
  "fallback_tools": [],
  "suggestion": null,
  "duration_ms": 35600
}
```

失败示例：

```json
{
  "status": "error",
  "tool": "image_to_video",
  "artifacts": [],
  "data": {},
  "error": {
    "code": "COMFYUI_TIMEOUT",
    "message": "ComfyUI 生成视频超时",
    "detail": "等待 120 秒未返回 history 结果"
  },
  "retryable": true,
  "fallback_tools": ["jimeng_generate_video"],
  "suggestion": "可以降低分辨率或切换即梦视频生成",
  "duration_ms": 120000
}
```

### 3.3 ToolResult 状态枚举

```text
success      工具成功，产物可用
error        工具执行失败
blocked      外部条件不满足，例如 ComfyUI 不可达
rejected     用户拒绝执行
canceled     用户取消或任务取消
partial      部分成功，例如 4 格图成功 3 格
```

### 3.4 ToolResult 标准化层

新增模块：

```text
backend/app/core/comic_chat_agent/tool_result.py
```

职责：

- 定义 `ToolResult`。
- 定义 `ArtifactPayload`。
- 提供 `normalize_tool_result(tool_name, raw_result)`。
- 兼容旧工具返回。
- 统一错误码。

---

## 4. TaskGraph 设计

### 4.1 TaskGraph 基本结构

```json
{
  "task_uid": "task_001",
  "goal": "生成一张仙侠图，转成视频，并配旁白",
  "steps": [
    {
      "step_uid": "s1",
      "title": "生成仙侠主图",
      "tool_name": "generate_image",
      "depends_on": [],
      "status": "pending"
    },
    {
      "step_uid": "s2",
      "title": "主图转动态视频",
      "tool_name": "image_to_video",
      "depends_on": ["s1"],
      "status": "pending"
    },
    {
      "step_uid": "s3",
      "title": "生成旁白音频",
      "tool_name": "text_to_speech",
      "depends_on": [],
      "status": "pending"
    },
    {
      "step_uid": "s4",
      "title": "合成音视频",
      "tool_name": "merge_media",
      "depends_on": ["s2", "s3"],
      "status": "pending"
    }
  ]
}
```

### 4.2 DAG 调度规则

```text
pending step
  ↓
所有 depends_on 都 succeeded
  ↓
ready
  ↓
TaskScheduler 选择 ready step
  ↓
running
  ↓
ToolResult success → succeeded
ToolResult error retryable → retry 或 replan
ToolResult error fatal → failed
ToolResult blocked → blocked
```

### 4.3 并行执行规则

如果多个 step 同时 ready，且工具风险等级允许自动执行：

```text
ready steps = [s2: image_to_video, s3: text_to_speech]
  ↓
并行执行
  ├── s2 生成视频
  └── s3 生成音频
  ↓
s4 merge_media 等待 s2 和 s3
```

这样能解决当前复杂链式任务中 TTS 与图生视频不能并行的问题。

### 4.4 Plan 生成策略

首期不需要完全依赖 LLM 规划，可采用“规则模板 + LLM 修正”的混合方案。

#### 规则模板

```text
文本含“图片/生成/画” → generate_image
文本含“视频/动态/动起来” → image_to_video
文本含“旁白/配音/语音” → text_to_speech
文本含“合成/成片/完整视频” → merge_media
文本含“高清/超分” → upscale_image
文本含“编辑/修改/改成” → edit_image
```

#### LLM 修正

LLM 只负责补充：

- step title。
- prompt。
- 参数。
- 风格。
- 是否需要并行。
- 是否需要额外步骤。

---

## 5. CompletionAuditor 设计

### 5.1 当前问题

当前完成判断依赖：

- `[TASK_DONE]`。
- 中文完成/未完成关键词。
- `has_plan` 正则。
- 前端扫描 assistant 文本。

这会导致误判。

### 5.2 新审计输入

```json
{
  "user_goal": "生成图片并转视频，加旁白",
  "task": {...},
  "steps": [...],
  "artifacts": [...],
  "last_llm_text": "...",
  "tool_invocations": [...]
}
```

### 5.3 新审计输出

```json
{
  "status": "incomplete",
  "complete": false,
  "reason": "视频和旁白步骤仍未完成",
  "completed_steps": ["s1"],
  "remaining_steps": ["s2", "s3", "s4"],
  "failed_steps": [],
  "blocked_steps": [],
  "next_action": {
    "type": "execute_step",
    "step_uid": "s2"
  }
}
```

### 5.4 审计规则

#### completed

```text
所有 required steps 均 succeeded
且 required artifacts 均 verified=true
```

#### incomplete

```text
仍有 pending/ready/running 的 required steps
```

#### blocked

```text
存在 blocked step，且没有 fallback 或需要用户输入
```

#### failed

```text
存在 failed step，且 retry_count >= max_retries，且无可用 fallback
```

#### canceled

```text
用户拒绝关键 step 或主动取消任务
```

### 5.5 LLM 审计的使用边界

LLM 可以用于生成解释，但不作为唯一判定来源。

```text
规则 Auditor 决定 status
LLM Reporter 负责把 status 解释成人话
```

---

## 6. Replanner / Recovery Policy 设计

### 6.1 Recovery 决策树

```text
ToolResult error
  ↓
error.retryable?
  ├── yes
  │   ├── retry_count < max_retries → retry same tool
  │   └── retry_count >= max_retries → fallback/replan
  │
  └── no
      ├── has fallback_tools → try fallback
      ├── needs user input → ask_user
      └── fatal → failed/block
```

### 6.2 常见错误策略

| 场景 | 错误码 | 策略 |
|---|---|---|
| ComfyUI 不可达 | `COMFYUI_UNAVAILABLE` | 尝试 Jimeng 或 blocked |
| ComfyUI 超时 | `COMFYUI_TIMEOUT` | 降低分辨率重试一次，再 fallback |
| 图生视频失败 | `I2V_FAILED` | 换视频工具或降低参数 |
| TTS 失败 | `TTS_FAILED` | 换 TTS 模型或返回可恢复错误 |
| LLM 403 | `LLM_FORBIDDEN` | 标记模型失败，建议切换模型 |
| 用户拒绝 | `USER_REJECTED` | 关键步骤 canceled；非关键步骤 skipped |
| 缺少图片输入 | `MISSING_IMAGE_INPUT` | 查找上一产物；没有则 ask_user |
| 文件不存在 | `FILE_NOT_FOUND` | 检查 artifact path；无法恢复则 blocked |

### 6.3 Fallback 工具映射

```json
{
  "generate_image": ["jimeng_generate_image"],
  "image_to_video": ["jimeng_generate_video"],
  "upscale_image": ["jimeng_upscale_image"],
  "edit_image": ["jimeng_edit_image"],
  "text_to_speech": []
}
```

### 6.4 Replanner 输出

```json
{
  "action": "fallback_tool",
  "step_uid": "s2",
  "from_tool": "image_to_video",
  "to_tool": "jimeng_generate_video",
  "reason": "ComfyUI 视频生成超时，切换到即梦视频生成"
}
```

或：

```json
{
  "action": "ask_user",
  "step_uid": "s2",
  "question": "图生视频失败，是否切换到即梦视频生成？",
  "choices": ["切换即梦", "降低参数重试", "跳过视频"]
}
```

---

## 7. WebSocket 事件协议设计

### 7.1 事件协议原则

- 所有事件必须带 `task_uid`。
- step 相关事件必须带 `step_uid`。
- `done` 必须带业务 `status`。
- 前端不再通过文本猜测完成状态。
- 事件 payload 结构化，避免字符串 JSON。

### 7.2 task_created

```json
{
  "type": "task_created",
  "task_uid": "task_001",
  "task": {
    "title": "仙侠图片转视频任务",
    "status": "planning",
    "user_goal": "生成一张仙侠图，转视频并配旁白"
  }
}
```

### 7.3 task_update

```json
{
  "type": "task_update",
  "task_uid": "task_001",
  "status": "running",
  "current_step_uid": "s2",
  "message": "正在执行：主图转动态视频"
}
```

### 7.4 step_update

```json
{
  "type": "step_update",
  "task_uid": "task_001",
  "step_uid": "s2",
  "step": {
    "title": "主图转动态视频",
    "tool_name": "image_to_video",
    "status": "running",
    "depends_on": ["s1"]
  }
}
```

### 7.5 tool_start

```json
{
  "type": "tool_start",
  "task_uid": "task_001",
  "step_uid": "s2",
  "tool_call_id": "call_001",
  "tool": "image_to_video",
  "input": {
    "image_path": "backend/uploads/agent_outputs/xxx.png",
    "prompt": "cinematic movement"
  }
}
```

### 7.6 tool_done

```json
{
  "type": "tool_done",
  "task_uid": "task_001",
  "step_uid": "s2",
  "tool_call_id": "call_001",
  "tool": "image_to_video",
  "result": {
    "status": "success",
    "artifacts": [
      {
        "type": "video",
        "url": "/uploads/agent_outputs/xxx.mp4",
        "file_path": "backend/uploads/agent_outputs/xxx.mp4"
      }
    ],
    "error": null
  }
}
```

### 7.7 artifact_created

```json
{
  "type": "artifact_created",
  "task_uid": "task_001",
  "step_uid": "s2",
  "artifact": {
    "artifact_uid": "a1",
    "type": "video",
    "url": "/uploads/agent_outputs/xxx.mp4",
    "verified": true
  }
}
```

### 7.8 approval_required

```json
{
  "type": "approval_required",
  "task_uid": "task_001",
  "step_uid": "s4",
  "tool_call_id": "call_004",
  "tool": "merge_media",
  "risk_level": "L1",
  "message": "即将合成音视频，是否继续？",
  "input_preview": {...}
}
```

### 7.9 incomplete

```json
{
  "type": "incomplete",
  "task_uid": "task_001",
  "status": "incomplete",
  "reason": "仍有步骤未完成",
  "completed_steps": ["s1"],
  "remaining_steps": ["s2", "s3", "s4"],
  "next_action": {
    "type": "execute_step",
    "step_uid": "s2"
  }
}
```

### 7.10 done

```json
{
  "type": "done",
  "task_uid": "task_001",
  "status": "completed",
  "final_report": {
    "summary": "已完成图片、视频、旁白和合成。",
    "completed_steps": [...],
    "failed_steps": [],
    "artifacts": [...]
  }
}
```

---

## 8. 后端模块改造设计

### 8.1 新增目录结构

```text
backend/app/core/comic_chat_agent/
├── agent_runner.py                  # 保留，逐步改为兼容入口
├── task_runtime/
│   ├── __init__.py
│   ├── models.py                    # Pydantic runtime models
│   ├── planner.py                   # TaskPlanner
│   ├── scheduler.py                 # TaskScheduler
│   ├── step_executor.py             # ReActStepExecutor
│   ├── auditor.py                   # CompletionAuditor
│   ├── replanner.py                 # Replanner
│   ├── reporter.py                  # FinalReport builder
│   ├── events.py                    # event builders
│   └── store.py                     # DB read/write
│
├── tool_result.py                   # ToolResult 标准化
├── tool_executor.py                 # 保留，返回逐步标准化
└── openai_client.py                 # 保留
```

### 8.2 Planner 设计

输入：

```python
@dataclass
class PlanningInput:
    user_goal: str
    style: str
    frames: int
    tts: bool
    auto_video: bool
    image_paths: list[str]
    model_config: ModelConfig
```

输出：

```python
@dataclass
class PlannedTask:
    task_type: str
    steps: list[PlannedStep]
```

Planner 首期策略：

```text
规则模板生成初稿
  ↓
LLM 补全标题、参数、prompt
  ↓
后端校验工具名和依赖
  ↓
写入 agent_steps
```

### 8.3 Scheduler 设计

职责：

- 找出 `ready` step。
- 判断并行执行条件。
- 判断审批状态。
- 控制最大并发数。

伪代码：

```python
def get_ready_steps(task_uid: str) -> list[AgentStep]:
    steps = store.list_steps(task_uid)
    succeeded = {s.step_uid for s in steps if s.status == "succeeded"}
    return [
        s for s in steps
        if s.status == "pending" and set(s.depends_on).issubset(succeeded)
    ]
```

### 8.4 ReActStepExecutor 设计

输入：

```text
当前 step
用户目标
上游 artifacts
可用工具 schema
对话摘要
```

Prompt 约束：

```text
你正在执行 TaskGraph 中的单个步骤。
只能完成当前 step，不要跳到其他 step。
如果当前 step 需要工具，必须返回 tool_call。
如果缺少输入，返回 structured_blocked，不要假装完成。
```

输出：

- `tool_call`。
- `blocked_reason`。
- `step_text`。

### 8.5 CompletionAuditor 设计

位置：

```text
每个 step 完成后运行
每轮无 tool_call 时运行
任务结束前运行
```

优先级：

```text
规则判定 > 结构化 TaskGraph > LLM 文本解释
```

### 8.6 Reporter 设计

Reporter 不判断状态，只根据 Auditor 结果生成报告。

FinalReport 结构：

```json
{
  "status": "completed",
  "summary": "任务已完成",
  "user_goal": "...",
  "completed_steps": [...],
  "failed_steps": [],
  "blocked_steps": [],
  "remaining_steps": [],
  "artifacts": [...],
  "next_recommendation": null
}
```

---

## 9. 前端改造设计

### 9.1 当前前端职责调整

当前前端做了很多推断：

- `inferIntent`
- `buildInitialPlan`
- `finalReportText`
- 文本扫描 TODO
- 根据 tool_done 字符串推断失败

优化后调整为：

```text
前端只做展示和交互
后端负责计划、状态、完成度和最终报告
```

### 9.2 前端状态模型

```ts
interface AgentTaskViewModel {
  id: string
  taskUid: string
  title: string
  userRequest: string
  taskType: string
  status: TaskStatus
  currentStepUid?: string
  steps: TaskStep[]
  artifacts: TaskArtifact[]
  logs: TaskLog[]
  finalReport?: FinalReport
}
```

### 9.3 事件处理调整

新增处理：

```text
task_created → 初始化 activeTask
task_update → 更新 task 状态
step_update → upsert step
artifact_created → upsert artifact
approval_required → 显示审批卡片
done → 展示后端 final_report
incomplete/blocked/failed → 展示后端原因和 remaining_steps
```

保留兼容：

```text
旧 tool_start/tool_done 事件继续支持
旧 done.metadata 继续支持
```

### 9.4 Final Report 改造

当前：

```text
前端 computed 拼接 finalReportText
```

改为：

```text
优先展示 event.final_report
没有 final_report 时才使用兼容 fallback
```

### 9.5 Plan 展示改造

当前：前端 `buildInitialPlan` 生成计划。

改为：后端 `task_created/step_update` 下发计划。

前端仍可保留 `buildInitialPlan` 作为连接前临时骨架，但一旦收到后端 task，就以服务端状态覆盖。

---

## 10. 安全与审批设计

### 10.1 工具风险等级

工具增加风险等级：

```text
L0：只读安全工具，可自动执行
L1：创作类工具，auto_mode 可自动执行
L2：写文件/执行代码/HTTP 请求，需要审批或策略判断
L3：高风险命令，默认禁止或强审批
```

### 10.2 工具风险字段入库

`ToolRegistry` 增加：

```json
{
  "risk_level": "L1",
  "requires_approval": false,
  "auto_mode_allowed": true,
  "input_artifact_types": ["image"],
  "output_artifact_types": ["video"],
  "fallback_tools": ["jimeng_generate_video"]
}
```

### 10.3 bash 安全策略

首期建议：

- 只允许只读命令自动执行。
- 禁止删除、移动、权限修改、后台进程等危险命令。
- 所有非只读 bash 必须审批。
- 命令执行必须限制 cwd。
- 记录完整 invocation。

### 10.4 文件写入策略

- 默认只允许写入项目允许目录。
- 禁止写入 `.env`、密钥文件、系统目录。
- 覆盖文件必须审批。
- 写入后自动生成 artifact 或 event。

---

## 11. 分期实施计划

## P0：状态权威化与 ToolResult 标准化

目标：解决任务完成判断不可靠问题。

### P0.1 新增 DB 表

- `agent_tasks`
- `agent_steps`
- `agent_artifacts`
- `agent_events`
- `tool_invocations`

### P0.2 新增运行时模型

文件：

```text
backend/app/core/comic_chat_agent/task_runtime/models.py
backend/app/core/comic_chat_agent/tool_result.py
```

### P0.3 ToolResult 标准化

改造：

- `execute_tool` 返回兼容旧格式，但额外提供标准结果。
- `tool_done` 事件携带结构化 `result`。
- 前端优先读取结构化 result。

### P0.4 TaskGraphStore

实现：

- 创建 task。
- 创建 steps。
- 更新 step 状态。
- 保存 artifact。
- 保存 event。

### P0.5 CompletionAuditor v1

规则版即可，不依赖 LLM。

判断：

- all required steps succeeded → completed。
- any blocked required step → blocked。
- any failed unrecoverable step → failed。
- remaining pending/ready/running → incomplete。

### P0.6 前端消费后端状态

- 新增 `task_created/task_update/step_update/artifact_created` 处理。
- `done` 优先使用后端 `status/final_report`。
- 保留旧逻辑兼容。

验收标准：

- 模型列出 TODO 但没有工具调用时，后端能明确返回 incomplete，并指出 remaining_steps。
- 生成图片但未转视频时，不能显示 completed。
- 工具失败时，Final Report 显示 failed step。
- 前端计划来自后端，不再只靠关键词猜测。

---

## P1：TaskPlanner + DAG Scheduler + Replanner

目标：让复杂创作任务可靠执行。

### P1.1 TaskPlanner v1

实现规则模板：

- 图片生成。
- 图片编辑。
- 图生视频。
- 旁白 TTS。
- 合成。
- 超分。

### P1.2 DAG Scheduler

实现：

- depends_on 判断。
- ready step 调度。
- 并行执行安全 step。
- 当前 step 状态同步。

### P1.3 ReActStepExecutor

把全局 ReAct 改造成 step 级执行：

- 当前 step prompt。
- 上游 artifact 注入。
- 工具调用必须绑定 step_uid。

### P1.4 Replanner v1

实现基本策略：

- retry。
- fallback tool。
- ask_user。
- blocked。

### P1.5 Orchestrator 合并

当前 `ComicOrchestrator` 不删除，而是变成 TaskGraph 的一个执行策略：

```text
多格独立图片 step group → parallel image generation executor
```

验收标准：

- `生成图片 → 转视频 → 旁白 → 合成` 能生成 DAG。
- TTS 和图生视频可以并行。
- image_to_video 失败后能重试或 fallback。
- 任务中断后可以通过 task_uid 查询状态。

---

## P2：安全模型、持久化恢复和产品化

目标：提升长期稳定性和安全性。

### P2.1 工具风险等级入库

- `risk_level`
- `auto_mode_allowed`
- `requires_approval`
- `input_artifact_types`
- `output_artifact_types`
- `fallback_tools`

### P2.2 断线恢复

前端重连后：

```text
GET /api/v1/comic-agent/tasks/{task_uid}
GET /api/v1/comic-agent/tasks/{task_uid}/events
```

恢复任务工作台。

### P2.3 事件回放

通过 `agent_events` 支持：

- 调试。
- 复盘。
- 自动化测试。
- 用户刷新页面恢复。

### P2.4 Smart 模式统一

`smart_agent_stream` 改为：

```text
IntentClassifier / RuleExecutor
```

不要再作为独立语义体系。

### P2.5 更强安全策略

- bash 命令解析。
- python_exec 沙箱。
- 文件路径限制。
- HTTP 域名限制。
- 高风险工具强审批。

验收标准：

- 刷新页面后任务状态可恢复。
- 所有工具调用有审计记录。
- 高风险工具不能绕过审批。
- Smart 与 Agent 使用统一事件协议。

---

## 12. 关键接口设计

### 12.1 WebSocket 输入

```json
{
  "message": "生成仙侠图片，转视频并配旁白",
  "model": "claude-sonnet-4-6",
  "style": "xianxia",
  "frames": 1,
  "auto_mode": true,
  "image_paths": []
}
```

### 12.2 继续任务输入

```json
{
  "action": "continue_task",
  "task_uid": "task_001"
}
```

### 12.3 审批输入

```json
{
  "action": "approve",
  "task_uid": "task_001",
  "step_uid": "s2",
  "tool_call_id": "call_001"
}
```

### 12.4 拒绝输入

```json
{
  "action": "reject",
  "task_uid": "task_001",
  "step_uid": "s2",
  "tool_call_id": "call_001",
  "reason": "不想生成视频"
}
```

### 12.5 查询任务

```http
GET /api/v1/comic-agent/tasks/{task_uid}
```

返回：

```json
{
  "task": {...},
  "steps": [...],
  "artifacts": [...],
  "events": [...]
}
```

---

## 13. Prompt 设计

### 13.1 TaskPlanner Prompt

```text
你是漫剧 Agent 的任务规划器。

你的任务是把用户目标拆成结构化步骤。
必须输出 JSON，不要输出解释。

要求：
1. 每个 step 只能对应一个清晰动作。
2. 如果步骤需要工具，填写 tool_name。
3. 如果步骤依赖上一步产物，填写 depends_on。
4. 图片转视频必须依赖图片产物。
5. 合成音视频必须依赖视频和音频产物。
6. 不要把“总结报告”作为创作工具步骤。

可用工具：
{tools}

用户目标：
{user_goal}

输出格式：
{
  "task_type": "...",
  "steps": [
    {
      "title": "...",
      "description": "...",
      "tool_name": "...",
      "depends_on": [],
      "inputs": {}
    }
  ]
}
```

### 13.2 ReActStepExecutor Prompt

```text
你正在执行一个 TaskGraph 中的单个步骤。

全局目标：{user_goal}
当前步骤：{step_title}
步骤描述：{step_description}
可用输入产物：{artifacts}
可用工具：{tools}

规则：
1. 只执行当前步骤，不要跳到其他步骤。
2. 如果当前步骤需要工具，必须返回 tool_call。
3. 如果缺少必要输入，返回 blocked，不要假装完成。
4. 不要只输出计划，必须行动。
5. 工具调用参数必须引用真实 artifact url/path。
```

### 13.3 Reporter Prompt

```text
你是漫剧 Agent 的最终报告生成器。

你不能改变任务状态，只能根据系统给定状态生成报告。

任务状态：{status}
用户目标：{user_goal}
已完成步骤：{completed_steps}
失败步骤：{failed_steps}
阻塞步骤：{blocked_steps}
剩余步骤：{remaining_steps}
产物：{artifacts}

请生成简洁、准确、不夸大、不把失败说成完成的最终报告。
```

---

## 14. 测试设计

### 14.1 单元测试

#### ToolResult 标准化

用例：

- generate_image 成功结果转标准 artifacts。
- image_to_video 错误结果转标准 error。
- TTS 空响应转 `TTS_EMPTY_RESPONSE`。
- 用户拒绝转 `rejected`。

#### CompletionAuditor

用例：

- 全部 step succeeded → completed。
- 仍有 pending → incomplete。
- failed 且不可恢复 → failed。
- blocked 且需要用户输入 → blocked。

#### Scheduler

用例：

- 无依赖 step ready。
- 依赖未完成 step 不 ready。
- 多个 ready step 可并行。
- failed dependency 阻止下游 step。

### 14.2 集成测试

#### 案例 1：单图生成

输入：

```text
生成一张仙侠女侠图片
```

预期：

- 创建 task。
- 创建 generate_image step。
- 产出 image artifact。
- task completed。

#### 案例 2：图片转视频

输入：

```text
生成一张仙侠图，并转成动态视频
```

预期：

- step1 generate_image。
- step2 image_to_video depends_on step1。
- 图片 artifact 作为 step2 输入。
- 最终 video artifact。

#### 案例 3：视频 + 旁白并行

输入：

```text
生成一张仙侠图，转视频，并生成一句旁白，最后合成
```

预期：

```text
generate_image
  ├── image_to_video
  └── text_to_speech
        ↓
     merge_media
```

#### 案例 4：工具失败恢复

模拟：`image_to_video` timeout。

预期：

- retry 一次。
- 仍失败则 fallback 或 blocked。
- FinalReport 不显示 completed。

#### 案例 5：无工具调用但仍有剩余步骤

模拟：LLM 输出“下一步需要生成视频”但无 tool_call。

预期：

- Auditor 根据 TaskGraph 判断 incomplete。
- 返回 remaining_steps。
- 前端显示未完成。

### 14.3 前端测试

- task_created 后创建工作台。
- step_update 后步骤状态准确。
- artifact_created 后结果区出现产物。
- done completed 后展示后端 final_report。
- incomplete 后展示 remaining_steps。
- blocked 后展示用户可选操作。

---

## 15. 迁移策略

### 15.1 兼容旧事件

短期保留：

- `thinking`
- `delta`
- `text`
- `tool_confirm`
- `tool_start`
- `tool_done`
- `incomplete`
- `done`

新增：

- `task_created`
- `task_update`
- `step_update`
- `artifact_created`
- `approval_required`
- `blocked`
- `failed`

### 15.2 兼容旧工具返回

`ToolResultNormalizer` 负责把旧结果转成新协议，避免一次性改完所有工具。

### 15.3 渐进替换 agent_stream

阶段：

```text
第一阶段：agent_stream 内创建 task/step，但仍走原循环
第二阶段：工具结果写入 AgentStep/Artifact
第三阶段：引入 CompletionAuditor 替代正则完成判断
第四阶段：引入 TaskPlanner 和 Scheduler
第五阶段：ReActStepExecutor 替代全局自由 ReAct
```

---

## 16. 文件改造清单

### 16.1 后端新增

```text
backend/app/core/comic_chat_agent/tool_result.py
backend/app/core/comic_chat_agent/task_runtime/models.py
backend/app/core/comic_chat_agent/task_runtime/store.py
backend/app/core/comic_chat_agent/task_runtime/planner.py
backend/app/core/comic_chat_agent/task_runtime/scheduler.py
backend/app/core/comic_chat_agent/task_runtime/step_executor.py
backend/app/core/comic_chat_agent/task_runtime/auditor.py
backend/app/core/comic_chat_agent/task_runtime/replanner.py
backend/app/core/comic_chat_agent/task_runtime/reporter.py
backend/app/core/comic_chat_agent/task_runtime/events.py
```

### 16.2 后端修改

```text
backend/app/api/v1/comic_agent.py
backend/app/core/comic_chat_agent/agent_runner.py
backend/app/core/comic_chat_agent/tool_executor.py
backend/app/core/comic_chat_agent/orchestrator.py
backend/app/models/agent_config.py 或新增 task models
backend/app/api/v1/workflows.py 可复用 DAG 思路
```

### 16.3 前端修改

```text
frontend/src/api/comic-agent.ts
frontend/src/views/comic-agent/ComicAgentView.vue
```

重点：

- 扩展 AgentEvent 类型。
- 消费 task/step/artifact 事件。
- FinalReport 使用后端数据。
- 保留旧事件兼容。

---

## 17. 最终目标验收标准

### 17.1 状态准确性

- `done completed` 只在所有 required steps 成功后发送。
- 有剩余步骤时必须是 `incomplete`，不能是 completed。
- 工具失败必须能定位到具体 step。
- 前端最终状态与后端 task.status 一致。

### 17.2 执行可靠性

- 复杂链式任务能按依赖执行。
- 可并行步骤能并行。
- 工具失败能 retry/fallback/block。
- 用户拒绝后不会无限重试。

### 17.3 产物可追踪性

- 每个图片/视频/音频都绑定 task 和 step。
- “继续执行”可以找到上一轮产物。
- FinalReport 能列出所有产物。

### 17.4 用户体验

- 前端展示后端真实计划。
- 任务进度清晰。
- 失败原因清晰。
- 剩余步骤清晰。
- 不再出现“明明没完成却显示已完成”。

---

## 18. 结论

漫剧 Agent 的优化重点不是继续堆更多工具，而是建立工程化 Agent 的核心控制层：

```text
TaskGraph
ToolResult
ArtifactMemory
CompletionAuditor
Replanner
FinalReport
```

当前系统已经有很好的基础：

- ReAct 主循环。
- 工具注册表。
- ComfyUI/Jimeng/TTS 多媒体工具。
- WebSocket 流式事件。
- 前端任务工作台。
- 工具审批和 auto_mode。

下一步应优先完成 P0：

```text
后端权威任务树 + 统一 ToolResult + CompletionAuditor + 前端消费后端状态
```

完成 P0 后，漫剧 Agent 将从“能调用工具的聊天式 Agent”，升级为“能判断任务是否真正完成的工程化创作 Agent”。

再完成 P1 后，系统将具备真正的复杂创作任务能力：

```text
生成图片 → 图生视频 / TTS 并行 → 合成 → 审计 → 报告
```

这就是 ttsapp 漫剧 Agent 从 ReAct Agent 进化到 Plan-and-Execute + Workflow Agent 的关键路径。
