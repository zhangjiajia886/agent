# 漫剧 Agent 深度分析

> 分析时间：2026 年 5 月  
> 分析对象：ttsapp 中 frontend 与 backend 的漫剧 Agent 架构、流程图、设计模式、优缺点与演进方向。  
> 对照基准：`主流agent知识体系.md` 中的三类主流 Agent 设计模式。

---

## 0. 总结结论

当前 ttsapp 漫剧 Agent 不是单一架构，而是一个混合型 Agent 系统：

```text
ttsapp 漫剧 Agent
├── 标准 ReAct Tool-Use Agent
│   └── agent_runner.py：LLM 思考 → 工具调用 → 结果观察 → 继续循环
│
├── Plan-and-Execute 雏形
│   ├── orchestrator.py：分镜规划 → 并行生成 → 汇总
│   └── ComicAgentView.vue：前端根据关键词生成展示型计划步骤
│
├── Workflow / DAG 能力外围系统
│   └── comic_engine / workflow editor：独立工作流 DAG 引擎，尚未深度合入当前 Agent 主循环
│
├── Computer-Use / Coding Agent 能力子集
│   └── bash/read_file/write_file/edit_file/python_exec/grep/list/http_request 等通用工具
│
└── 多媒体创作执行器
    ├── ComfyUI 工具
    ├── Jimeng 即梦工具
    ├── TTS 工具
    └── 媒体合成工具
```

用 `主流agent知识体系.md` 的标准评价：

| 体系 | 当前成熟度 | 评价 |
|---|---:|---|
| **ReAct Tool-Use Agent** | 75% | 已具备主循环、工具注册、流式 FC、工具审批、工作记忆、空工具审计，但停止控制仍不够结构化 |
| **Plan-and-Execute / Workflow Agent** | 45% | 有并行分镜编排器和前端计划展示，但缺后端持久化 TaskGraph，复杂任务仍依赖模型自然语言记忆 |
| **Computer-Use / Coding Workspace Agent** | 40% | 有通用工具和安全审批雏形，但缺完整的代码库索引、测试闭环、沙箱和工程级状态管理 |
| **多媒体创作 Agent 专项能力** | 65% | 工具体系丰富，支持 ComfyUI/即梦/TTS/上传图片，但产物链、依赖关系和失败恢复仍弱 |

一句话判断：

> ttsapp 漫剧 Agent 已经从“聊天机器人”升级到了“可调用工具的创作型 ReAct Agent”，但还没有完全升级为“显式任务树 + 产物记忆 + 完成度审计 + 可恢复工作流”的工程化 Agent。

---

## 1. 当前后端架构流程图

### 1.1 WebSocket 总入口流程

核心文件：

- `backend/app/api/v1/comic_agent.py`
- `backend/app/core/comic_chat_agent/agent_runner.py`
- `backend/app/core/comic_chat_agent/orchestrator.py`
- `backend/app/core/comic_chat_agent/tool_executor.py`
- `backend/app/core/comic_chat_agent/openai_client.py`

整体流程：

```text
Frontend ComicAgentView.vue
  ↓ WebSocket
/api/v1/comic-agent/ws/chat
  ↓
鉴权 token
  ↓
获取 / 创建 AgentConversation
  ↓
接收用户 message + style + frames + model + auto_mode + image_paths
  ↓
保存 user message 到 DB
  ↓
判断执行模式
  ├── 没有 model_id
  │   └── smart_agent_stream：关键词/规则型轻量 Agent
  │
  ├── frames > 1 且 style != auto
  │   └── ComicOrchestrator：并行漫剧模式
  │       ├── LLM 分镜规划
  │       ├── 并行 generate_image
  │       ├── 汇总成功/失败格数
  │       └── done
  │
  └── 标准 Agent 模式
      └── agent_stream：ReAct 工具循环
          ├── 加载模型配置 ModelConfig
          ├── 加载 ToolRegistry → OpenAI tools schema
          ├── 加载 AgentPrompt system prompt
          ├── 构造 messages
          ├── LLM streaming + tool_calls
          ├── 工具审批
          ├── execute_tool
          ├── observation 写回 messages
          ├── 工作记忆 artifacts 注入
          ├── 空工具审计
          └── done / incomplete / error
```

### 1.2 标准 ReAct Agent 循环

`agent_runner.py` 的核心循环：

```text
agent_stream(user_message, model_config, db, history, approval_queue, auto_mode)
  ↓
create_llm_client(model_config)
  ↓
build_tool_definitions(db)
  ↓
load_system_prompt(db)
  ↓
build_messages(system_prompt, history, user_message)
  ↓
for iteration in MAX_ITERATIONS:
    注入工作记忆 artifacts
    检查 token 预算，必要时 compact history
    如果达到最大轮次，进入 summary round
    调用 llm.chat_stream_with_tools
    累积 delta / thinking / tool_calls
    如果没有 tool_calls：
        做 task_done / wrap_up / has_plan / incomplete 检测
        第一次空工具 → 注入系统审计提示
        审计后仍未完成 → yield incomplete
        完成或总结轮 → break
    如果有 tool_calls：
        记录 assistant tool_calls
        对每个工具：
            检查调用次数上限
            判断是否需要审批
            等待 approve/reject
            execute_tool
            yield tool_done
            compact result 写回 messages
            收集 image/video/audio/file 到 artifacts
  ↓
yield done(metadata)
```

这符合 `主流agent知识体系.md` 中的 ReAct 结构：

```text
Thought → Action → Observation → Thought → Action/Finish
```

但当前 Thought 不是独立结构化状态，而是由模型文本、thinking、system prompt 和正则共同驱动。

### 1.3 工具执行器架构

核心文件：`tool_executor.py`

```text
execute_tool(name, params)
  ↓
TOOL_ALIASES 标准化工具名
  ↓
TOOL_EXECUTORS 分发表
  ├── 漫剧工具
  │   ├── generate_image
  │   ├── generate_image_with_face
  │   ├── edit_image
  │   ├── image_to_video
  │   ├── text_to_video
  │   ├── upscale_image
  │   ├── text_to_speech
  │   ├── merge_media
  │   └── add_subtitle
  │
  ├── 即梦工具
  │   ├── jimeng_generate_image
  │   ├── jimeng_reference_image
  │   ├── jimeng_edit_image
  │   ├── jimeng_upscale_image
  │   ├── jimeng_generate_video
  │   └── jimeng_motion_mimic
  │
  └── 通用工具
      ├── bash
      ├── read_file
      ├── write_file
      ├── edit_file
      ├── python_exec
      ├── web_search
      ├── web_fetch
      ├── grep_search
      ├── find_files
      ├── list_dir
      └── http_request
```

工具执行器体现了以下设计模式：

- **Registry Pattern**：`TOOL_EXECUTORS` 工具注册表。
- **Adapter Pattern**：把 ComfyUI、Jimeng、TTS、系统工具统一包装成 `dict → dict`。
- **Alias Normalization**：`TOOL_ALIASES` 兼容模型输出的不同工具命名。
- **Facade Pattern**：Agent 只面对 `execute_tool`，不关心底层 ComfyUI/Jimeng/本地命令细节。

---

## 2. 当前前端架构流程图

核心文件：

- `frontend/src/views/comic-agent/ComicAgentView.vue`
- `frontend/src/api/comic-agent.ts`

### 2.1 前端消息与 WebSocket 流程

```text
用户输入
  ↓
handleSend / sendQuickPrompt
  ↓
sendToAgent(text)
  ├── createTask(text)
  │   ├── inferIntent(text)
  │   └── buildInitialPlan(text)
  │
  ├── messages push user message
  ├── 确保 WebSocket 连接
  ├── 收集 uploaded image_paths
  └── agentWS.send(message, options)
      ├── style
      ├── frames
      ├── model
      ├── tts
      ├── autoVideo
      ├── auto_mode
      └── image_paths
```

### 2.2 前端事件处理流程

```text
WebSocket event
  ↓
handleAgentEvent(event)
  ├── thinking
  │   ├── addTaskLog
  │   └── 更新 currentStage
  │
  ├── delta / text
  │   └── 追加 assistant message
  │
  ├── tool_confirm
  │   ├── ensureToolStep
  │   ├── step.status = awaiting_approval
  │   └── 显示确认 UI
  │
  ├── tool_start
  │   ├── ensureToolStep
  │   ├── step.status = running
  │   └── startElapsedTimer
  │
  ├── tool_done
  │   ├── 匹配对应 tool_start / step
  │   ├── 根据 result 判断 failed/completed
  │   ├── 提取 image_url/video_url/audio_url
  │   └── addArtifact
  │
  ├── incomplete
  │   ├── activeTask.status = failed
  │   └── 显示未完成错误
  │
  ├── error
  │   └── activeTask.status = failed
  │
  └── done
      ├── 结束 streaming
      ├── 基于步骤/产物/文本 TODO 判断 completed 或 failed
      └── 显示 Final Report
```

### 2.3 前端设计模式

| 模块 | 使用模式 | 说明 |
|---|---|---|
| `ComicAgentWS` | WebSocket Client Wrapper | 封装连接、发送、事件回调 |
| `handleAgentEvent` | Event Dispatcher | 按事件类型分发 UI 状态更新 |
| `activeTask` | ViewModel / Client-side State Machine | 前端维护任务、步骤、产物、日志 |
| `buildInitialPlan` | Rule-based Planner | 用关键词生成展示型任务计划 |
| `ensureToolStep` | Step Reconciliation | 后端真实工具事件与前端计划步骤对齐 |
| `finalReportText` | Derived State | 根据前端状态生成总结报告 |

前端已经具备“任务工作台”雏形，但它的计划和状态主要是前端本地推断，不是后端权威 TaskGraph。

---

## 3. 当前实际使用了哪些设计模式

### 3.1 ReAct Pattern

体现位置：`agent_runner.py`

特征：

- LLM 读 messages 和 tools。
- 返回 delta/thinking/tool_calls。
- 后端执行工具。
- 工具结果以 tool message 形式回填。
- 下一轮 LLM 基于 observation 决定继续或结束。

评价：这是当前漫剧 Agent 的主架构。

### 3.2 Function Calling / Tool Registry Pattern

体现位置：

- `build_tool_definitions(db)`
- `ToolRegistry`
- `TOOL_EXECUTORS`
- `TOOL_ALIASES`

优势：

- 工具 schema 来自 DB，可配置。
- 执行器和工具定义分离。
- 新增工具成本较低。

不足：

- 工具之间的依赖关系不在 schema 中表达。
- 工具结果没有统一强类型结构。
- 工具成功条件依赖后端和前端各自判断。

### 3.3 Strategy Pattern

体现位置：

```text
if model_id:
    if use_parallel:
        ComicOrchestrator
    else:
        agent_stream
else:
    smart_agent_stream
```

不同执行策略：

- Smart 模式：规则/关键词轻量 Agent。
- 标准 Agent：ReAct 工具循环。
- 并行漫剧模式：Plan → Parallel Execute → Summary。

### 3.4 Orchestrator / Pipeline Pattern

体现位置：`orchestrator.py`

流程：

```text
分镜规划 → 并行图像生成 → 汇总输出
```

这是明显的 Plan-and-Execute 雏形。

优点：

- 对多格漫剧比普通 ReAct 更稳定。
- 速度快，可并行生成。
- 前端能按 frame 精确匹配 tool_done。

不足：

- 只覆盖 `frames > 1 && style != auto` 的场景。
- 只适合“多格图片生成”，不覆盖“图片→视频→旁白→合成”的复杂链式任务。
- 不是通用 TaskGraph。

### 3.5 Observer / Event Sourcing 雏形

体现位置：WebSocket event 流。

事件类型：

- `thinking`
- `delta`
- `text`
- `tool_confirm`
- `tool_start`
- `tool_done`
- `incomplete`
- `error`
- `done`

优点：

- 前端可以实时显示执行过程。
- 有利于调试和用户信任。
- 支持审批和长任务进度。

不足：

- 事件没有严格 schema 版本。
- `done` 缺少明确 `status`。
- `tool_done.result` 是字符串 JSON，前端需要正则/JSON 解析混用。
- 前端 Final Report 仍大量依赖本地 computed 拼接。

### 3.6 Approval / Safety Gate Pattern

体现位置：`needs_approval()` 与 `approval_queue`。

三级审批：

```text
L0 自动执行：只读工具
L1 auto_mode 自动执行：创作类工具 / 安全写入 / python_exec
L2 必须确认：高风险或未归类工具
```

优点：

- 比简单“所有工具都确认”更可用。
- 避免审批疲劳。
- 保留高风险操作控制。

不足：

- `bash` 在集合定义和逻辑中存在边界不一致：`CREATIVE_AUTO_APPROVE_TOOLS` 未包含 bash，但 `needs_approval` 内有 bash 只读判断分支，实际可能不会触发。
- 缺少更细粒度命令审计 AST/allowlist。
- 缺少每个工具的风险等级字段统一从 DB 下发。

### 3.7 Client-side Task ViewModel Pattern

体现位置：`ComicAgentView.vue`

前端维护：

- `AgentTaskViewModel`
- `TaskStep`
- `TaskArtifact`
- `TaskLog`

优点：

- UI 体验比纯聊天强很多。
- 能显示 Plan、Execution、Result、Final Report。
- 能汇总图片、视频、音频产物。

不足：

- 这是“展示型状态”，不是后端权威状态。
- `buildInitialPlan` 用关键词猜测，容易与真实 LLM 工具计划不一致。
- 步骤依赖关系不存在。
- 无法可靠判断复杂任务完成度。

---

## 4. 按主流 Agent 知识体系逐项对比

## 4.1 体系一：ReAct Tool-Use Agent 对比

### 标准 ReAct 要求

来自 `主流agent知识体系.md`：

```text
messages + tools → LLM
  ├── 返回文本
  └── 返回 tool_calls
工具结果 append 到 messages
继续下一轮
```

### ttsapp 当前实现

当前实现基本符合：

- `openai_client.py` 支持 OpenAI 兼容流式 Function Calling。
- `agent_runner.py` 支持 tool_calls 累积和 XML `<tool_call>` 降级解析。
- `execute_tool` 统一执行工具。
- 工具结果压缩后写回 messages。
- 支持多轮循环，最大 15 轮。
- 支持 token 压实。
- 支持工作记忆 artifacts 注入。
- 支持工具审批。
- 支持空工具审计和 `incomplete` 事件。

### 优点

#### 1. 工具体系丰富

当前工具已经覆盖：

- 图像生成。
- 图像编辑。
- 图生视频。
- 文生视频。
- 超分。
- TTS。
- 媒体合成。
- 字幕。
- 即梦工具。
- 文件读写。
- 代码执行。
- 网络搜索。
- HTTP 请求。

这使它明显超越普通聊天助手。

#### 2. 具备真实 ReAct 循环

不是一次性问答，而是：

```text
LLM → tool_call → execute → observation → LLM → next tool
```

这对复杂创作任务是必要基础。

#### 3. 已经意识到空工具问题

当前已经加入：

- `no_tool_reviewed`
- 系统审计提示
- `incomplete` 事件
- 前端 incomplete 处理

这说明系统开始从“空工具=结束”升级为“空工具=审计”。

#### 4. 有工具调用上限

`MAX_TOOL_CALLS_PER_TOOL` 防止单工具失控循环。

#### 5. 有媒体工作记忆

`artifacts` 收集图片/视频/音频/文件，并每轮注入。

这对“生成图片后转视频”非常关键。

### 弊端

#### 1. 完成判断仍依赖自然语言正则

当前 no-tool 分支依赖：

```text
任务已完成 / 已全部完成 / TASK_DONE
如果你需要 / 你也可以
剩余 TODO / 尚未完成 / 下一步
```

这属于启发式判断。复杂任务中会出现：

- 模型写了“总结”，但其实没完成。
- 模型写了“下一步”，但没调工具。
- 模型写了“已生成”，但工具实际失败。
- 前端和后端对状态理解不一致。

根因：没有结构化 `TaskGraph` 作为完成度依据。

#### 2. 审计仍由同一个 LLM 自评

空工具审计提示让模型自我判断，但模型可能继续犯同样错误：

```text
第一次：我还有 TODO，但没有工具调用
第二次：我还有 TODO，但仍没有工具调用
```

当前处理是发 `incomplete`，这是正确止损，但不是完整解决。

更理想做法：

- 用结构化任务状态检查器判断缺失步骤。
- 如果下一步工具明确，由后端构造下一轮执行上下文。
- 如果模型不返回工具，标记具体 blocked step。

#### 3. Observation 不够强类型

工具结果压缩成自然语言字符串：

```text
[generate_image] ✓ | 图片URL: ... | 图片路径: ...
```

虽然节省 token，但也带来问题：

- LLM 需要从文本中理解产物。
- 后端没有统一验证产物是否可用。
- 前端需要从字符串正则提取 URL。

建议增加结构化 Observation：

```json
{
  "tool": "generate_image",
  "status": "success",
  "artifacts": [{"type": "image", "url": "...", "path": "..."}],
  "error": null
}
```

#### 4. ReAct 主循环没有显式 Step 概念

当前工具调用是“工具级历史”，不是“任务步骤级状态”。

因此后端不知道：

- 这个 `generate_image` 属于第几步？
- 这个 `image_to_video` 依赖哪张图？
- 用户要求的旁白是否完成？
- 工具失败后是该重试、跳过还是终止？

#### 5. API 失败与任务失败混在一起

例如 LLM 403：

```text
LLM 调用失败: 403 Forbidden
```

后端会 yield `error` 并 return，但业务层没有生成结构化失败报告：

```text
status = failed
failed_reason = llm_api_403
completed_steps = [...]
remaining_steps = [...]
```

这导致前端只能显示错误，无法准确说明“哪些任务已完成，哪些未完成”。

### ReAct 体系评分

| 维度 | 评分 | 说明 |
|---|---:|---|
| Tool Calling | 8/10 | 工具丰富，流式 FC 和 XML 降级都具备 |
| Observation | 6/10 | 有结果压缩，但不够结构化 |
| Reflection | 6/10 | 有空工具审计，但仍依赖 LLM 自评 |
| Stop Control | 5/10 | 比之前进步，但仍依赖正则和前端兜底 |
| Memory | 6/10 | 有 artifacts，但缺 step-level memory |
| Recovery | 5/10 | 有拒绝和工具上限，缺系统化重试/降级策略 |

---

## 4.2 体系二：Plan-and-Execute / Workflow Agent 对比

### 标准 Plan-and-Execute 要求

```text
用户目标
  ↓
Planner 生成结构化任务树
  ↓
Executor 按任务树逐步执行
  ↓
每步执行后更新状态
  ↓
必要时 Replanner 重规划
  ↓
最终报告
```

### ttsapp 当前实现形态

当前有三个 Plan-and-Execute 雏形：

#### 1. `orchestrator.py` 并行漫剧模式

```text
Phase 1: LLM 生成分镜 JSON
Phase 2: 并行 generate_image
Phase 3: 汇总结果
```

这是最接近 Plan-and-Execute 的后端模块。

#### 2. 前端 `buildInitialPlan`

前端根据关键词生成：

- 生成首版视觉结果。
- 执行图像编辑。
- 制作动态视频。
- 生成旁白音频。

但它只是 UI 计划，不是后端执行计划。

#### 3. 独立 DAG 工作流引擎

项目中已有 Workflow/DAG 引擎能力，但当前漫剧 Agent 主循环没有把任意复杂用户任务自动编译成 DAG 执行。

### 优点

#### 1. 并行分镜编排器方向正确

对 4 格/6 格漫剧，ReAct 一格一格生成效率低。`ComicOrchestrator` 用：

```text
一次规划 → 多图并发 → 进度流式返回
```

这是非常适合漫剧场景的架构。

#### 2. 有阶段化执行意识

`orchestrator.py` 明确写了：

- Phase 1：分镜规划。
- Phase 2：并行图像生成。
- Phase 3：汇总输出。

这比普通 ReAct 更稳定、更可控。

#### 3. 前端已经按任务工作台展示

前端有：

- 需求理解。
- Plan。
- Execution。
- Result Analysis。
- Final Report。

这非常接近 Workflow Agent 的用户体验。

### 弊端

#### 1. 缺后端权威 TaskGraph

复杂任务应该是：

```json
{
  "goal": "图片→视频→旁白",
  "steps": [
    {"id": "s1", "tool": "generate_image", "status": "succeeded"},
    {"id": "s2", "tool": "image_to_video", "depends_on": ["s1"], "status": "pending"},
    {"id": "s3", "tool": "text_to_speech", "status": "pending"}
  ]
}
```

当前没有这样的后端结构。

导致：

- 完成度无法精确判断。
- 依赖关系无法表达。
- 失败恢复无法定位到步骤。
- “继续”时只能靠历史文本和 artifacts。

#### 2. 前端 Plan 与后端真实执行脱节

前端 `buildInitialPlan` 是规则生成的：

```text
文本含“图片” → 加 generate_image
文本含“视频” → 加 image_to_video
文本含“旁白” → 加 text_to_speech
```

但后端 LLM 可能：

- 先调用 web_search。
- 选择 jimeng_generate_image 而不是 generate_image。
- 生成多张图。
- 跳过某个前端预设步骤。
- 调用工具失败但文本说成功。

因此前端计划不是执行真相，只是展示辅助。

#### 3. Orchestrator 只适合固定多格生图

它不能处理任意复杂链：

```text
搜索资料 → 写脚本 → 生图 → 图生视频 → TTS → 合成 → 字幕
```

当前标准 ReAct 能处理开放任务，但不稳定；Orchestrator 稳定但窄。

理想架构应该把二者融合：

```text
TaskPlanner 生成通用 TaskGraph
  ↓
如果是多格独立图片 → 并行 Executor
如果是链式依赖任务 → 顺序 Executor
如果有可并行分支 → DAG Executor
```

#### 4. 没有 Replanner

当某一步失败，比如：

- image_to_video 失败。
- TTS 返回空错误。
- LLM API 403。
- ComfyUI 不可达。

系统没有结构化重规划：

```text
失败 step = image_to_video
原因 = ComfyUI timeout
替代方案 = jimeng_generate_video / 降低分辨率 / 询问用户
```

当前更多依赖 LLM 下一轮自然语言判断。

### Plan-and-Execute 体系评分

| 维度 | 评分 | 说明 |
|---|---:|---|
| Planner | 5/10 | 有 prompt 规划和前端规则计划，但缺通用结构化 Planner |
| TaskGraph | 2/10 | 后端主 Agent 基本没有持久化任务树 |
| Executor | 6/10 | 工具执行能力强，但不是按任务图执行 |
| Dependency | 3/10 | 主要靠 artifacts 和模型文本传递 |
| Replanner | 3/10 | 失败后重规划弱 |
| Progress UI | 7/10 | 前端展示优秀，但状态权威性不足 |

---

## 4.3 体系三：Computer-Use / Coding Workspace Agent 对比

### 标准 Computer-Use Agent 要求

```text
理解需求
  ↓
搜索/读取环境
  ↓
操作文件/终端/浏览器/API
  ↓
运行验证
  ↓
读取日志
  ↓
修复错误
  ↓
最终交付
```

### ttsapp 当前能力

当前 Agent 有通用工具：

- `bash`
- `read_file`
- `write_file`
- `edit_file`
- `python_exec`
- `web_search`
- `web_fetch`
- `grep_search`
- `find_files`
- `list_dir`
- `http_request`

这使漫剧 Agent 具备 Coding Agent 的一部分能力。

### 优点

#### 1. 工具面覆盖较完整

相较只会生成图片的创作 Agent，ttsapp 漫剧 Agent 能读写文件、跑 Python、查网页、调 API。

这意味着它可以完成：

- 生成脚本。
- 读取项目文件。
- 搜索资料。
- 写入素材说明。
- 执行辅助处理。
- 调试简单问题。

#### 2. 有安全审批雏形

只读工具自动执行，高风险工具需要确认，符合 Coding Agent 的基本安全模型。

#### 3. 有工作区文件能力

`python_exec` 已改为 backend 目录作为 cwd，避免之前 `/tmp` 上下文错位。

### 弊端

#### 1. 缺少“工程闭环”

Claude Code 类系统强调：

```text
搜索 → 读文件 → 修改 → 测试 → 读日志 → 修复 → 总结
```

当前漫剧 Agent 虽然有工具，但 system prompt 和状态机没有强制形成工程闭环。

例如：

- 调用 `write_file` 后不一定 `read_file` 验证。
- 调用 `python_exec` 后不一定分析 exit code。
- 调用 `bash` 后不一定根据 stderr 修复。
- API 失败不一定有替代路径。

#### 2. 缺少沙箱与权限模型

`bash` 和 `python_exec` 是强能力工具，需要更严谨：

- 命令白名单/黑名单。
- 工作目录限制。
- 文件写入目录限制。
- 网络请求域名限制。
- 超时与资源限制。
- 命令解释预览。

当前只有基础阻断和审批，不够工程级。

#### 3. 缺少代码库索引和语义搜索

Claude Code / Windsurf / Cursor 的核心是代码上下文检索。

当前 Agent 只有 grep/find/list/read 等工具，没有：

- repo index。
- symbol index。
- AST 级编辑。
- 多文件依赖分析。
- 测试影响范围分析。

#### 4. 与漫剧创作主线耦合不清

通用工具能力强，但模型可能滥用：

- 明明工作记忆有图片路径，却重新 `find_files`。
- 明明有专用 `read_file`，却用 bash cat。
- 明明该调用 `image_to_video`，却开始 list_dir 找图。

虽然 system prompt 已规定工具优先级，但没有硬性 planner 约束。

### Computer-Use 体系评分

| 维度 | 评分 | 说明 |
|---|---:|---|
| 文件工具 | 6/10 | 读写编辑具备，但不够 AST/patch 化 |
| 终端工具 | 5/10 | 有 bash/python，但沙箱不足 |
| 搜索能力 | 5/10 | 有 grep/find/web_search，缺语义索引 |
| 验证闭环 | 3/10 | 没有强制测试/日志验证模式 |
| 安全控制 | 5/10 | 有审批，但策略还粗 |
| 工程交付 | 4/10 | 可辅助，但不是专职 Coding Agent |

---

## 5. 按完整 Agent 核心模块逐项评估

根据 `主流agent知识体系.md` 的完整 Agent 模块：

```text
Intent Router
Planner
Executor
Tool Registry
Memory
Observer
Reflector / Critic
Recovery
Stop Controller
Reporter
```

### 5.1 Intent Router

当前实现：

- 后端：`model_id` 决定 ReAct/Smart。
- 后端：`frames > 1 && style != auto` 决定并行模式。
- 前端：`inferIntent` 基于关键词生成任务类型。
- Smart 模式：`_detect_intent` 规则分发。

优点：

- 简单直接。
- 对常见创作任务有效。
- 能区分聊天与工具任务。

弊端：

- 多处重复判断。
- 前后端意图分类可能不一致。
- 不支持结构化置信度。
- “继续”这种跨轮指令很难准确理解。

建议：

- 后端统一提供 `IntentClassification`。
- 前端只展示后端分类结果。
- 对“继续”必须结合当前任务状态，而不是单独理解文本。

### 5.2 Planner

当前实现：

- system prompt 要求模型拆分任务。
- orchestrator 对多格漫剧做分镜规划。
- 前端 buildInitialPlan 做展示计划。

优点：

- 已经具备任务拆分意识。
- 分镜规划较适合漫剧场景。

弊端：

- 标准 ReAct 模式没有结构化计划对象。
- 计划无法持久化。
- 计划与真实工具调用无法一一绑定。

建议：

- 新增后端 `AgentTask` / `AgentStep`。
- 首轮先生成结构化任务树。
- 每次工具调用必须绑定 step_id。

### 5.3 Executor

当前实现：

- `execute_tool` 分发。
- ComfyUI/Jimeng/TTS/local/http 多后端。

优点：

- 执行能力强。
- 工具覆盖广。
- 支持异步执行。

弊端：

- 执行器只知道工具，不知道业务 step。
- 缺少统一结果标准。
- 工具失败格式不完全一致。

建议：

- 统一 `ToolResult` schema。
- 每个工具返回 `status/artifacts/error/suggestion/retryable`。

### 5.4 Tool Registry

当前实现：

- DB `ToolRegistry`。
- `build_tool_definitions` 动态构建 OpenAI tools。
- `TOOL_EXECUTORS` 执行器注册。

优点：

- 可配置。
- 易扩展。
- 支持模型动态加载工具。

弊端：

- DB 工具定义与 Python executor 分离，可能不一致。
- 工具风险等级没有完全结构化。
- 工具依赖/产物类型没有表达。

建议：

为每个工具增加：

```json
{
  "risk_level": "L0/L1/L2",
  "input_artifact_types": ["image"],
  "output_artifact_types": ["video"],
  "retry_policy": {...},
  "success_contract": {...}
}
```

### 5.5 Memory

当前实现：

- 对话历史 DB 保存。
- `build_messages` 加载最近历史。
- `_compact_history` 压缩。
- `artifacts` 工作记忆。
- 前端 `activeTask.artifacts`。

优点：

- 已保留媒体 URL。
- 已避免压缩时丢媒体路径。
- 支持上传图片路径注入。

弊端：

- artifacts 是字符串列表，不是结构化对象。
- 没有跨轮持久化的 `ArtifactMemory` 表。
- “继续”时不能可靠绑定上一轮产物。
- 图片路径、视频路径、音频路径与 step 关系不稳定。

建议：

新增：

```text
agent_tasks
agent_steps
agent_artifacts
```

让每个产物归属到 step。

### 5.6 Observer

当前实现：

- 工具结果 compact 后写入 messages。
- 前端解析 `tool_done`。
- 根据 result 正则判断失败。

优点：

- 能实时显示产物。
- 对图片/视频/音频有 UI 提取。

弊端：

- 成功/失败判断分散在后端和前端。
- 前端靠字符串正则识别错误。
- 没有强制检查文件是否存在、可下载、可播放。

建议：

- 后端统一判断 ToolResult。
- 前端只消费结构化字段。
- 媒体工具应返回 `verified=true/false`。

### 5.7 Reflector / Critic

当前实现：

- LLM 自然语言反思。
- 空工具审计提示。
- incomplete 文本检测。

优点：

- 已经开始处理“空工具不等于完成”。

弊端：

- 反思不是结构化 JSON。
- 审计没有单独模型/规则校验器。
- 未对照原始需求逐项验收。

建议：

新增 `CompletionAuditor`：

```text
输入：user_goal + task_graph + artifacts + last_text
输出：complete / incomplete / blocked / failed + remaining_steps
```

### 5.8 Recovery

当前实现：

- 工具调用次数限制。
- 拒绝工具提示。
- ComfyUI 健康检查。
- 部分工具错误信息增强。

优点：

- 防死循环能力增强。
- 用户拒绝不会无限 force。
- ComfyUI 不可用能提前报错。

弊端：

- 没有统一 retry policy。
- 没有 fallback tool policy。
- 没有 failed step 的重规划策略。
- LLM API 403 直接失败，无模型降级。

建议：

```text
ToolResult.error
  ├── retryable=true → 最多重试 N 次
  ├── fallback_tool=xxx → 尝试替代工具
  ├── user_action_required → 询问用户
  └── fatal → 标记 failed
```

### 5.9 Stop Controller

当前实现：

- `MAX_ITERATIONS`。
- summary round。
- task_done 正则。
- wrap_up 正则。
- incomplete 正则。
- 前端 done 再判断 TODO。

优点：

- 比早期明显更强。
- 能防止无限循环。
- 能识别部分未完成情况。

弊端：

- 没有权威完成状态。
- `done` 事件不一定代表 completed。
- 前端需要二次猜测。
- summary round 可能把“部分完成”包装成“结束”。

建议：

后端事件协议改为：

```json
{"type": "done", "status": "completed"}
{"type": "done", "status": "failed"}
{"type": "done", "status": "blocked"}
{"type": "incomplete", "remaining_steps": [...]}
```

### 5.10 Reporter

当前实现：

- LLM 输出 delta/text。
- 前端 `finalReportText` 根据本地状态生成最终报告。

优点：

- UI 结构清晰。
- 有任务状态、执行结果、产物统计。

弊端：

- 前端报告不是后端真实审计报告。
- 容易出现“执行失败，但总结说本轮任务已经结束”。
- 对 remaining TODO 展示不够结构化。

建议：

由后端生成权威 `FinalReport`：

```json
{
  "status": "blocked",
  "completed_steps": [...],
  "failed_steps": [...],
  "remaining_steps": [...],
  "artifacts": [...],
  "next_recommendation": "..."
}
```

---

## 6. 当前漫剧 Agent 的主要优点

### 6.1 已有真正的工具型 Agent 基础

不是简单调用 ComfyUI，而是具备：

- LLM 大脑。
- DB 工具注册。
- Function Calling。
- 工具执行器。
- 多轮 ReAct。
- WebSocket 流式事件。

这是进一步工程化的基础。

### 6.2 工具生态扩展性强

通过 `ToolRegistry + TOOL_EXECUTORS + TOOL_ALIASES`，可以持续增加：

- ComfyUI 工作流。
- 即梦 API。
- TTS。
- 文件工具。
- 搜索工具。
- HTTP 工具。

### 6.3 多媒体创作链已经打通一部分

已经支持：

- 文生图。
- 图生视频。
- TTS。
- 媒体合成。
- 上传参考图。
- 即梦生图。

这使其具备“漫剧创作 Agent”的业务特征。

### 6.4 有并行生成优化

`ComicOrchestrator` 对多格漫画采用并行生成，比普通串行 ReAct 更适合生产。

### 6.5 前端 UX 具备任务工作台形态

前端已经不是普通聊天框，而是：

- 需求理解。
- 计划。
- 执行。
- 结果。
- 总结。
- 工具审批。
- 自动执行开关。
- 附件上传。

这非常接近专业 Agent 产品形态。

### 6.6 已经开始处理 Agent 最难的问题

包括：

- 空工具审计。
- 未完成事件。
- 工具拒绝。
- 工具调用上限。
- token 压缩。
- 媒体工作记忆。
- thinking 噪音过滤。

这些都是 Agent 工程化中的关键点。

---

## 7. 当前漫剧 Agent 的核心弊端

### 7.1 最大问题：没有后端权威任务树

这是所有复杂任务问题的根因。

当前任务状态分散在：

- LLM 自然语言。
- messages 历史。
- artifacts 字符串。
- 前端 activeTask。
- DB conversation message。

但没有一个权威对象表示：

```text
用户目标是什么？
拆成几个步骤？
每个步骤状态是什么？
每个步骤输入输出是什么？
哪个步骤失败？
剩余 TODO 是什么？
```

### 7.2 Plan 和 Execution 没有绑定

模型说：

```text
第 1 步生成图片，第 2 步转视频，第 3 步配音
```

但后端没有把这三步落成结构化状态。

所以当模型只完成第 1 步后，系统只能靠文本判断还有第 2/3 步。

### 7.3 完成判断仍然脆弱

当前完成判断是：

```text
正则 + no_tool_reviewed + 前端 TODO 文本检测
```

这比之前好，但仍不是工程级。

工程级应该是：

```text
所有 required steps status == succeeded
且所有 required artifacts verified == true
→ completed
```

### 7.4 前端状态不是权威状态

前端 `buildInitialPlan` 是 UI 计划，不是后端计划。

这会导致：

- 前端显示 1/2 完成，但后端真实任务可能是 3 步。
- 前端把某个工具映射错 step。
- done 后前端自己猜 completed/failed。

### 7.5 工具结果协议不统一

当前工具结果可能是：

```json
{"status": "success", "image_url": "..."}
{"success": true, "path": "..."}
{"ok": true, "path": "..."}
{"error": "..."}
{"status": "failed"}
```

这对 Agent 和前端都不友好。

### 7.6 复杂链式任务不稳定

典型任务：

```text
生成图片 → 图生视频 → 生成旁白 → 合成视频
```

当前问题：

- 生成图片后，不一定自动图生视频。
- 图生视频需要正确传 image_path，模型可能丢路径。
- TTS 失败后恢复弱。
- 最后合成是否执行没有结构化检查。
- 任一环节失败后，最终报告可能不准确。

### 7.7 API/模型错误没有纳入任务状态

例如 LLM 403：

- 实际是模型调用失败。
- 前端显示执行失败。
- 但任务报告仍可能有“工具调用已停止，任务结束”。

应区分：

```text
completed：业务完成
failed：执行失败
blocked：外部依赖阻塞
canceled：用户取消
incomplete：仍有未执行 TODO
```

### 7.8 Smart 模式与 Agent 模式割裂

无 model_id 时走 `smart_agent_stream`，有 model_id 时走 ReAct。

Smart 模式是规则模拟/轻量流程，和真实 Agent 能力差异大，可能导致用户体验不一致。

---

## 8. 与主流产品/框架的横向比较

### 8.1 对比 Claude Code

| 项目 | Claude Code 类 | ttsapp 漫剧 Agent |
|---|---|---|
| 核心目标 | 工程任务闭环 | 多媒体创作 + 工具调用 |
| 搜索/读取 | 强 | 中等 |
| 修改/执行 | 强 | 中等 |
| 测试验证 | 强 | 弱 |
| 状态管理 | 工作区 + tool trace | messages + 前端状态 |
| 停止判断 | 通过测试/目标验证 | 正则 + LLM 审计 |
| 安全 | 命令审批较严格 | 三级审批雏形 |

结论：

> ttsapp 不需要完全变成 Claude Code，但需要学习它的“执行后验证”和“状态权威在系统侧”的思想。

### 8.2 对比 OpenClaw / Workflow Agent

| 项目 | OpenClaw-like | ttsapp 漫剧 Agent |
|---|---|---|
| TaskGraph | 核心 | 缺失 |
| Planner/Executor 分离 | 明确 | 部分存在 |
| Step 状态 | 后端持久化 | 前端临时维护 |
| 失败重规划 | 核心能力 | 弱 |
| 可观察轨迹 | 强 | WebSocket 事件较强 |
| 复杂长任务 | 适合 | 不稳定 |

结论：

> ttsapp 最应该补的是 OpenClaw 类的 TaskGraph 和 Replanner。

### 8.3 对比 Manus / Devin 类长任务 Agent

| 项目 | Manus/Devin 类 | ttsapp 漫剧 Agent |
|---|---|---|
| 自主长任务 | 强 | 中等偏弱 |
| 用户无需频繁继续 | 是 | 仍可能需要 |
| 环境操作 | 浏览器/终端/文件 | 文件/终端/API 有一部分 |
| 任务持久化 | 强 | 会话消息为主 |
| 产物交付 | 明确 | 媒体产物有，但链式交付弱 |

结论：

> ttsapp 已有长任务雏形，但缺“任务不因一次 WebSocket/LLM 调用结束而丢失”的持久化执行模型。

### 8.4 对比 LangGraph

LangGraph 的关键是显式状态机：

```text
State → Node → Edge → State
```

当前 ttsapp 是：

```text
messages → LLM → tools → messages
```

缺少明确 State。

建议借鉴：

```text
AgentState = {
  task_graph,
  messages,
  artifacts,
  current_step,
  errors,
  user_approvals
}
```

---

## 9. 推荐目标架构

### 9.1 漫剧 Agent vNext 架构

```text
ComicAgent vNext
├── IntentClassifier
│   └── 输出 task_type / confidence / required_capabilities
│
├── TaskPlanner
│   └── user_goal → AgentTask + AgentStep[]
│
├── TaskGraphStore
│   ├── agent_tasks
│   ├── agent_steps
│   └── agent_artifacts
│
├── ReActStepExecutor
│   ├── 给 LLM 当前 step + 可用工具
│   ├── 要求返回 tool_call
│   └── 工具结果绑定 step_id
│
├── ToolExecutor
│   └── 统一 ToolResult schema
│
├── Observer
│   └── 校验工具结果与产物可用性
│
├── CompletionAuditor
│   └── 对照 task_graph 判断 completed/blocked/failed/incomplete
│
├── Replanner
│   └── 失败后重试/换工具/降级/询问用户
│
└── Reporter
    └── 生成权威最终报告
```

### 9.2 推荐后端状态结构

```python
class AgentTask:
    id: str
    conversation_id: int
    user_goal: str
    task_type: str
    status: Literal["running", "completed", "failed", "blocked", "canceled", "incomplete"]
    current_step_id: str | None
    summary: str | None

class AgentStep:
    id: str
    task_id: str
    title: str
    tool: str | None
    status: Literal["pending", "ready", "running", "succeeded", "failed", "blocked", "skipped"]
    depends_on: list[str]
    inputs: dict
    outputs: dict
    error: str | None
    retry_count: int

class AgentArtifact:
    id: str
    task_id: str
    step_id: str
    type: Literal["image", "video", "audio", "file"]
    url: str
    path: str | None
    verified: bool
    metadata: dict
```

### 9.3 推荐事件协议

```json
{
  "type": "task_update",
  "task": {
    "id": "task_x",
    "status": "running",
    "current_step_id": "step_2"
  }
}
```

```json
{
  "type": "step_update",
  "step": {
    "id": "step_2",
    "title": "图片转动态视频",
    "status": "running",
    "tool": "image_to_video"
  }
}
```

```json
{
  "type": "artifact_created",
  "artifact": {
    "type": "video",
    "url": "/uploads/agent_outputs/xxx.mp4",
    "step_id": "step_2"
  }
}
```

```json
{
  "type": "done",
  "status": "completed",
  "completed_steps": 3,
  "remaining_steps": [],
  "artifacts": [...]
}
```

```json
{
  "type": "incomplete",
  "status": "blocked",
  "completed_steps": ["生成图片"],
  "remaining_steps": ["图片转视频", "生成旁白"],
  "reason": "模型未返回下一步工具调用"
}
```

---

## 10. 改造优先级

### P0：建立后端权威任务树

目标：解决“任务到底完成没完成”的根因。

需要：

- `AgentTask`。
- `AgentStep`。
- `AgentArtifact`。
- 每个工具调用绑定 step。
- 前端计划改为消费后端 task state。

### P0：统一 ToolResult schema

所有工具统一返回：

```json
{
  "status": "success/error/rejected/blocked",
  "artifacts": [],
  "data": {},
  "error": null,
  "suggestion": null,
  "retryable": false
}
```

### P0：CompletionAuditor 模块化

不要只靠正则和 LLM 自评。

Auditor 输入：

- 用户原始目标。
- TaskGraph。
- ToolResults。
- Artifacts。
- Last LLM text。

输出：

- completed。
- incomplete。
- blocked。
- failed。
- remaining_steps。
- next_action。

### P1：把复杂创作任务编译成 DAG

例如：

```text
生成图片
  ├── 图生视频
  └── 生成旁白
        ↓
     合成音视频
```

这样 TTS 可以和图生视频并行。

### P1：Replanner / Recovery Policy

规则：

- ComfyUI 不可达 → 尝试 Jimeng 或 blocked。
- image_to_video 失败 → 降低参数重试一次。
- TTS 失败 → 换 TTS 模型或返回可恢复错误。
- LLM 403 → 标记模型失败，建议切换模型。

### P1：前端 Final Report 改为后端权威报告

前端不要再拼：

```text
本轮任务已经结束，工具调用已停止...
```

而是展示后端 `final_report`。

### P2：Smart 模式和 Agent 模式统一

Smart 模式可以保留，但应作为：

```text
IntentClassifier / RuleExecutor
```

而不是独立的一套事件语义。

### P2：增强安全模型

- 工具风险等级入库。
- bash 命令解析。
- python_exec 沙箱。
- 文件写入目录限制。
- HTTP 域名限制。

---

## 11. 最终评价

### 当前优点

- 已具备真实 ReAct Agent 主循环。
- 工具生态丰富，覆盖多媒体创作和通用操作。
- WebSocket 事件流和前端任务工作台体验较好。
- 有并行漫剧生成优化。
- 有工具审批和自动执行模式。
- 已开始处理空工具审计、未完成状态、媒体工作记忆等高级 Agent 问题。

### 当前弊端

- 缺后端权威 TaskGraph。
- 计划、执行、产物、完成判断没有统一状态源。
- 完成判断仍依赖自然语言正则和前端兜底。
- 工具结果协议不统一。
- 复杂链式创作任务不稳定。
- 失败恢复和重规划能力弱。
- 前端任务计划只是展示型推断，不是执行真相。
- Computer-Use 能力有工具但缺工程闭环。

### 核心改造方向

```text
当前：ReAct + 工具 + 前端展示型计划

目标：TaskGraph + ReAct Step Executor + ArtifactMemory + CompletionAuditor + Replanner
```

也就是从：

```text
LLM 自己记住下一步
```

升级为：

```text
系统显式知道下一步
```

这是漫剧 Agent 从“能调用工具”走向“能可靠完成复杂创作任务”的关键分水岭。
