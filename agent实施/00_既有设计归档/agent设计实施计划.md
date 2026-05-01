# Agent 设计实施计划

> 生成时间：2026 年 5 月  
> 依据文档：`漫剧agent深度优化设计.md`、`主流agent对比.md`、`漫剧agent优化TODO.md`。  
> 当前状态：P0 最小状态闭环已实现，后续重点是把内存态 Runtime 升级为可持久化、可调度、可恢复、可审计的工程化 Agent Runtime。

---

## 0. 总体目标

当前 P0 已经完成：

```text
RuntimeTask / RuntimeStep
  ↓
ReAct 工具执行
  ↓
ToolResult 标准化
  ↓
Artifact 事件
  ↓
P0 audit_task
  ↓
done.final_report
```

但它仍然是一个“最小闭环”，不是完整 vNext。

完整目标是：

```text
用户目标
  ↓
TaskPlanner 生成结构化 TaskGraph
  ↓
TaskStore 持久化任务、步骤、产物、事件、工具调用
  ↓
TaskScheduler 调度 ready steps
  ↓
ReActStepExecutor 执行单步
  ↓
ToolExecutor 返回统一 ToolResult
  ↓
Observer 校验产物
  ↓
CompletionAuditor 权威审计
  ↓
Replanner 处理失败/阻塞/重试/降级/询问用户
  ↓
Reporter 生成 FinalReport
  ↓
Frontend Workbench 展示权威状态
```

核心原则：

```text
Agent 可靠性的核心不是 prompt，而是系统状态。
```

---

## 1. 当前实现基线

### 1.1 已完成的 P0 能力

| 能力 | 当前状态 | 文件 |
|---|---|---|
| DB 模型定义 | 已完成模型文件，但未写入业务数据 | `backend/app/models/agent_task.py` |
| ToolResult 标准化 | 已完成基础标准化 | `backend/app/core/comic_chat_agent/tool_result.py` |
| 内存态任务图 | 已完成 P0 RuntimeTask/RuntimeStep | `backend/app/core/comic_chat_agent/task_runtime.py` |
| AgentRunner 接入 | 已接入 task/step/artifact/final_report 事件 | `backend/app/core/comic_chat_agent/agent_runner.py` |
| 前端事件类型 | 已扩展 | `frontend/src/api/comic-agent.ts` |
| 前端工作台消费 | 已接入新增事件 | `frontend/src/views/comic-agent/ComicAgentView.vue` |
| 进度管理 | 已创建 | `漫剧agent优化TODO.md` |

### 1.2 已验证

- 后端 Python 编译检查通过。
- 前端 `npx vite build` 通过。
- `npm run build` 的 `vue-tsc` 在 Node v25 下存在兼容错误，不归因于本次代码。

### 1.3 当前限制

P0 仍有以下限制：

- Task/Step/Artifact/Event/ToolInvocation **没有持久化写入数据库**。
- `task_runtime.py` 还是单文件内存运行时，不是完整模块目录。
- 还没有真正 `TaskScheduler`。
- 还没有 `Replanner`。
- 还没有断线恢复和事件回放。
- CompletionAuditor 仍是 P0 简化规则。
- Frontend 已消费后端事件，但仍保留部分旧前端推断逻辑。

---

## 2. 目标模块结构

最终建议把当前单文件 `task_runtime.py` 演进为目录模块：

```text
backend/app/core/comic_chat_agent/task_runtime/
├── __init__.py
├── models.py          # Runtime Pydantic/dataclass 模型
├── planner.py         # TaskPlanner
├── scheduler.py       # TaskScheduler
├── step_executor.py   # ReActStepExecutor
├── auditor.py         # CompletionAuditor
├── replanner.py       # Replanner / RecoveryPolicy
├── reporter.py        # FinalReportBuilder
├── events.py          # WebSocket event builders
├── store.py           # DB persistence
└── observer.py        # Artifact/ToolResult verification
```

现有文件保留原则：

```text
agent_runner.py        保留为兼容入口，逐步变薄
openai_client.py       保留
工具 executor.py       保留，但逐步要求返回 ToolResult 或可被 normalize
tool_result.py         保留，可继续增强
```

---

## 3. 阶段路线图

### P0.5：补齐 P0 验证与小修

目标：确认现有 P0 不破坏旧功能，并清理明显兼容问题。

#### TODO

- [ ] 启动后端，确认新表能自动创建。
- [ ] 打开前端，确认普通聊天不受影响。
- [ ] 执行“生成一张图”任务，确认前端收到：
  - [ ] `task_created`
  - [ ] `step_update`
  - [ ] `tool_done.standard_result`
  - [ ] `artifact_created`
  - [ ] `done.final_report`
- [ ] 执行工具失败场景，确认 step 进入 `failed`。
- [ ] 执行只列计划不调工具场景，确认前端不误判完成。
- [ ] 修复 `vue-tsc` 与 Node v25 的环境兼容问题。
- [ ] 更新 `漫剧agent优化TODO.md` 的 P0 验收勾选状态。

#### 验收标准

- [ ] P0 所有新增事件前端能正常消费。
- [ ] 旧版 `tool_start/tool_done/delta/done` 流程不受影响。
- [ ] 没有 Python 编译错误。
- [ ] Vite 构建通过。

---

### P1：状态持久化与事件落库

目标：从“内存态任务状态”升级为“数据库权威状态”。

#### 3.1 Store 层设计

新增：

```text
backend/app/core/comic_chat_agent/task_runtime/store.py
```

职责：

- 创建 `AgentTask`。
- 创建和更新 `AgentStep`。
- 创建 `AgentArtifact`。
- 写入 `AgentEvent`。
- 写入 `ToolInvocation`。
- 查询任务详情。
- 查询任务事件流。
- 支持从 DB 重建 RuntimeTask。

建议接口：

```python
class AgentTaskStore:
    async def create_task(input: CreateTaskInput) -> AgentTask: ...
    async def create_steps(task_uid: str, steps: list[PlannedStep]) -> list[AgentStep]: ...
    async def update_task_status(task_uid: str, status: str, **kwargs) -> None: ...
    async def update_step_status(step_uid: str, status: str, **kwargs) -> None: ...
    async def create_artifact(task_uid: str, step_uid: str | None, artifact: dict) -> AgentArtifact: ...
    async def append_event(task_uid: str | None, step_uid: str | None, event_type: str, payload: dict) -> AgentEvent: ...
    async def create_tool_invocation(...) -> ToolInvocation: ...
    async def finish_tool_invocation(...) -> None: ...
    async def load_task_graph(task_uid: str) -> RuntimeTask: ...
```

#### 3.2 事件落库策略

每个 WebSocket 事件发送前都通过统一方法：

```python
async def emit(event: dict):
    await store.append_event(...)
    yield event
```

事件入库规则：

| 事件 | 是否落库 | 原因 |
|---|---|---|
| `task_created` | 是 | 恢复任务入口 |
| `task_update` | 是 | 状态变化 |
| `step_update` | 是 | 步骤状态变化 |
| `tool_start` | 是 | 工具调用审计 |
| `tool_done` | 是 | 工具调用结果 |
| `artifact_created` | 是 | 产物追踪 |
| `approval_required` | 是 | 人工介入记录 |
| `delta` | 可选 | 文本流量大，P1 可不落库 |
| `thinking` | 可选 | 可只保留摘要 |
| `done` | 是 | 最终状态和报告 |

#### 3.3 AgentRunner 改造

P1 不要求完全重写 `agent_runner.py`，先做兼容改造：

```text
agent_runner.py
  ↓
创建 DB AgentTask
  ↓
创建 DB AgentStep
  ↓
每次状态变化更新 DB
  ↓
每次事件写 AgentEvent
  ↓
每次工具调用写 ToolInvocation
```

#### TODO

- [ ] 新建 `task_runtime/store.py`。
- [ ] 定义 `CreateTaskInput`、`CreateStepInput` 等内部数据结构。
- [ ] `agent_runner.py` 创建任务时写入 `AgentTask`。
- [ ] P0 RuntimeStep 同步写入 `AgentStep`。
- [ ] `ToolResult.artifacts` 写入 `AgentArtifact`。
- [ ] `tool_start/tool_done` 写入 `ToolInvocation`。
- [ ] WebSocket 事件写入 `AgentEvent`。
- [ ] 增加任务详情 API：`GET /api/v1/comic-agent/tasks/{task_uid}`。
- [ ] 增加任务事件 API：`GET /api/v1/comic-agent/tasks/{task_uid}/events`。
- [ ] 增加会话任务列表 API：`GET /api/v1/comic-agent/conversations/{id}/tasks`。

#### 验收标准

- [ ] 刷新页面后能通过 API 查到历史任务。
- [ ] 任务的 step/artifact/tool_invocation/event 均可查询。
- [ ] `done.final_report` 存入 `AgentTask.final_report`。
- [ ] 工具失败能在 `AgentStep.error` 和 `ToolInvocation.error` 中看到。

---

### P2：TaskPlanner 与 TaskGraph 明确化

目标：不再只靠关键词生成 RuntimeStep，而是生成结构化 TaskGraph。

#### 4.1 Planner 设计

新增：

```text
backend/app/core/comic_chat_agent/task_runtime/planner.py
```

Planner 输入：

```python
@dataclass
class PlanningInput:
    user_goal: str
    style: str
    frames: int
    tts: bool
    auto_video: bool
    image_paths: list[str]
    selected_model: str
    available_tools: list[ToolRegistry]
```

Planner 输出：

```python
@dataclass
class PlannedStep:
    step_uid: str
    title: str
    description: str
    step_type: str
    tool_name: str | None
    depends_on: list[str]
    inputs: dict
    required: bool
    sort_order: int
```

首期策略：

```text
规则模板生成基础 TaskGraph
  ↓
工具可用性校验
  ↓
LLM 补充 prompt/参数/标题
  ↓
后端校验并落库
```

#### 4.2 典型模板

##### 单图生成

```text
s1 generate_image
```

##### 图生视频

```text
s1 generate_image
s2 image_to_video depends_on s1
```

##### 图片 + 视频 + 旁白 + 合成

```text
s1 generate_image
s2 image_to_video depends_on s1
s3 text_to_speech
s4 merge_media depends_on s2,s3
```

##### 多格漫剧

```text
s1 plan_storyboard
s2 generate_image frame=1 depends_on s1
s3 generate_image frame=2 depends_on s1
s4 generate_image frame=3 depends_on s1
s5 generate_image frame=4 depends_on s1
s6 merge_comic depends_on s2,s3,s4,s5
```

#### TODO

- [ ] 新建 `planner.py`。
- [ ] 定义 `PlanningInput`、`PlannedTask`、`PlannedStep`。
- [ ] 实现规则模板 Planner。
- [ ] 实现工具可用性校验。
- [ ] 支持 `frames/style/tts/autoVideo/image_paths`。
- [ ] 将 Planner 输出写入 `AgentStep.depends_on/inputs/metadata`。
- [ ] 前端 `task_created` 展示真实计划而不是临时骨架。

#### 验收标准

- [ ] “生成图片并转视频配旁白”能生成 4 个带依赖的步骤。
- [ ] 多格任务能生成并行图片步骤。
- [ ] 缺少工具时任务进入 `blocked` 或 `ask_user`，不是继续假装执行。

---

### P3：TaskScheduler 与 StepExecutor

目标：从“LLM 自由决定下一步”升级为“系统调度 ready step，LLM 只执行当前 step”。

#### 5.1 Scheduler 设计

新增：

```text
backend/app/core/comic_chat_agent/task_runtime/scheduler.py
```

核心规则：

```text
pending step
  ↓
所有 depends_on 均 succeeded
  ↓
ready
  ↓
风险策略允许
  ↓
running
```

接口：

```python
class TaskScheduler:
    async def get_ready_steps(task_uid: str) -> list[AgentStep]: ...
    async def mark_ready_steps(task_uid: str) -> list[AgentStep]: ...
    async def select_next_steps(task_uid: str, max_parallel: int) -> list[AgentStep]: ...
    async def has_unfinished_required_steps(task_uid: str) -> bool: ...
```

#### 5.2 StepExecutor 设计

新增：

```text
backend/app/core/comic_chat_agent/task_runtime/step_executor.py
```

StepExecutor 输入：

```text
当前 step
用户目标
上游 artifacts
可用工具 schema
对话摘要
```

StepExecutor 约束：

```text
只能完成当前 step。
不能跳到其他 step。
如果缺输入，返回 blocked。
如果需要工具，必须返回 tool_call。
```

#### 5.3 与 ReAct 的关系

旧模式：

```text
LLM 自己决定整个任务下一步
```

新模式：

```text
Scheduler 决定当前 step
LLM 只决定当前 step 的工具参数
```

#### TODO

- [ ] 新建 `scheduler.py`。
- [ ] 新建 `step_executor.py`。
- [ ] 实现 ready step 计算。
- [ ] 实现 step 级 prompt。
- [ ] 实现 step 级工具调用。
- [ ] 支持并行 ready steps 的顺序执行版本。
- [ ] 后续再升级为真正 asyncio 并行。
- [ ] `agent_runner.py` 逐步改为调用 Scheduler + StepExecutor。

#### 验收标准

- [ ] 用户说“图片转视频配音”，系统不会在图片未生成前执行视频步骤。
- [ ] TTS 与图生视频在依赖满足时可并行或顺序自动执行。
- [ ] LLM 即使输出计划，也不会绕过 TaskGraph 状态。

---

### P4：CompletionAuditor 独立化

目标：最终状态必须由系统根据 TaskGraph 判定，而不是由模型文本判定。

#### 6.1 Auditor 输入

```python
@dataclass
class AuditInput:
    task: AgentTask
    steps: list[AgentStep]
    artifacts: list[AgentArtifact]
    tool_invocations: list[ToolInvocation]
    last_llm_text: str | None
```

#### 6.2 Auditor 输出

```python
@dataclass
class AuditResult:
    status: Literal['completed', 'incomplete', 'blocked', 'failed', 'canceled']
    complete: bool
    reason: str
    completed_steps: list[str]
    remaining_steps: list[str]
    failed_steps: list[str]
    blocked_steps: list[str]
    next_action: dict | None
```

#### 6.3 规则优先级

```text
用户取消 > failed 不可恢复 > blocked 需用户输入 > incomplete > completed
```

#### TODO

- [ ] 新建 `auditor.py`。
- [ ] 从 `task_runtime.audit_task` 迁移规则。
- [ ] 增加 required step 判定。
- [ ] 增加 required artifact verified 判定。
- [ ] 增加 partial 成功判定。
- [ ] 增加 LLM Reporter 解释，但不让 LLM 决定状态。

#### 验收标准

- [ ] 有 required step 未完成时，绝不输出 completed。
- [ ] 工具失败且不可恢复时，输出 failed。
- [ ] 缺用户输入时，输出 blocked/ask_user。
- [ ] 所有 required steps 和 artifacts 完成时，输出 completed。

---

### P5：Replanner / RecoveryPolicy

目标：工具失败后不再只靠 LLM 自己想办法，而是由策略驱动恢复。

#### 7.1 Replanner 输入

```python
@dataclass
class ReplanInput:
    task: AgentTask
    failed_step: AgentStep
    tool_result: ToolResult
    available_tools: list[ToolRegistry]
    artifacts: list[AgentArtifact]
```

#### 7.2 Replanner 输出

```python
@dataclass
class ReplanDecision:
    action: Literal['retry', 'fallback_tool', 'ask_user', 'skip', 'block', 'fail']
    step_uid: str
    reason: str
    next_tool: str | None
    patched_inputs: dict | None
    question: str | None
    choices: list[str] | None
```

#### 7.3 策略表

| 场景 | 策略 |
|---|---|
| ComfyUI 不可达 | fallback 到即梦，或 blocked |
| ComfyUI 超时 | 降低参数 retry 一次，再 fallback |
| 图生视频失败 | fallback 到即梦视频 |
| TTS 失败 | 换模型或 ask_user |
| 缺图片输入 | 从 ArtifactMemory 查找上游图片；没有则 ask_user |
| 用户拒绝关键步骤 | canceled |
| 用户拒绝非关键步骤 | skipped 或 ask_user |

#### TODO

- [ ] 新建 `replanner.py`。
- [ ] 定义 fallback 工具映射。
- [ ] 将 `ToolResult.retryable/fallback_tools` 纳入决策。
- [ ] 实现 retry same tool。
- [ ] 实现 fallback_tool。
- [ ] 实现 ask_user 事件。
- [ ] 实现 block/fail 最终判定。
- [ ] 前端支持 `ask_user` 或复用审批面板。

#### 验收标准

- [ ] `image_to_video` 失败后能建议或自动切换 `jimeng_generate_video`。
- [ ] `generate_image` 失败后能 fallback 到 `jimeng_generate_image`。
- [ ] 缺少输入时不会伪造路径，而是 ask_user。
- [ ] 连续失败不会无限循环。

---

### P6：断线恢复、事件回放、任务控制

目标：让长任务具备工程可恢复性。

#### 8.1 断线恢复

机制：

```text
前端 reconnect
  ↓
携带 task_uid 或 conversation_id
  ↓
后端查询 AgentEvent
  ↓
回放事件重建前端工作台
  ↓
如果任务仍 running，继续监听或恢复调度
```

#### 8.2 任务控制 API

新增：

```text
POST /api/v1/comic-agent/tasks/{task_uid}/cancel
POST /api/v1/comic-agent/tasks/{task_uid}/retry
POST /api/v1/comic-agent/tasks/{task_uid}/resume
GET  /api/v1/comic-agent/tasks/{task_uid}
GET  /api/v1/comic-agent/tasks/{task_uid}/events
GET  /api/v1/comic-agent/tasks/{task_uid}/artifacts
```

#### TODO

- [ ] 事件回放 API。
- [ ] 前端重连后拉取事件。
- [ ] 任务取消 API。
- [ ] 任务重试 API。
- [ ] 任务恢复 API。
- [ ] 前端任务控制按钮。
- [ ] 后端运行中任务注册表。

#### 验收标准

- [ ] 页面刷新后可恢复任务步骤和产物。
- [ ] WebSocket 断开后可重新连接并查看任务状态。
- [ ] 用户可取消长任务。
- [ ] 失败步骤可单独重试。

---

### P7：可观测性与 Tracing

目标：让 Agent 的每一步都可复盘、可统计、可优化。

#### 9.1 Trace 数据

记录：

- LLM 输入摘要。
- LLM 输出摘要。
- tool_call 参数。
- ToolResult。
- step 状态变化。
- Replanner 决策。
- Auditor 决策。
- token 用量。
- duration。

#### 9.2 前端面板

新增任务详情抽屉：

```text
任务概览
步骤 DAG
事件时间线
工具调用记录
产物列表
错误与恢复记录
最终报告
```

#### TODO

- [ ] 扩展 `ToolInvocation` 记录 duration/token/error_code。
- [ ] 增加 `AgentEvent` 筛选查询。
- [ ] 前端新增事件时间线。
- [ ] 前端新增工具调用详情。
- [ ] 统计任务成功率、失败率、平均耗时。

#### 验收标准

- [ ] 任意任务可按时间线复盘。
- [ ] 任意失败可定位到 step/tool/error。
- [ ] 可统计工具失败率和任务完成率。

---

### P8：LangGraph-like 演进评估

目标：在业务状态稳定后，再评估是否引入 LangGraph 或自研 StateGraph 抽象。

#### 10.1 推荐路线

当前不建议直接替换为 LangChain Agent。

推荐：

```text
业务状态：ttsapp AgentTaskGraph
运行时思想：LangGraph-like State / Node / Edge / Checkpoint
工具层：ttsapp ToolExecutor
前端：ttsapp Workbench
```

#### 10.2 可选方案

##### 路线 A：继续自研

优点：

- 贴合业务。
- 迁移风险低。
- 可控性强。

缺点：

- 调度器和 checkpoint 需要自己维护。

##### 路线 B：局部接入 LangGraph

方式：

```text
LangGraph StateGraph 负责 runtime flow
每个 node 读写 ttsapp DB
ToolExecutor 仍用自研
```

适用时机：

- P1-P7 已稳定。
- 状态模型已清晰。
- 需要更复杂条件边和恢复能力。

#### TODO

- [ ] 梳理当前 TaskGraph 与 LangGraph StateGraph 的映射。
- [ ] 做一个实验性 branch。
- [ ] 实现 planner → executor → auditor → replanner → reporter 的 LangGraph demo。
- [ ] 对比自研 scheduler 与 LangGraph 的复杂度。
- [ ] 决定是否正式接入。

---

## 4. 完整 TODO 总表

### P0.5 验证

- [ ] 后端启动验证新表创建。
- [ ] WebSocket 普通问答验证。
- [ ] WebSocket 工具任务验证。
- [ ] 工具失败验证。
- [ ] 不调用工具误完成验证。
- [ ] 修复/规避 `vue-tsc` 与 Node v25 兼容问题。

### P1 持久化

- [ ] `store.py`
- [ ] `AgentTask` 写入
- [ ] `AgentStep` 写入
- [ ] `AgentArtifact` 写入
- [ ] `AgentEvent` 写入
- [ ] `ToolInvocation` 写入
- [ ] 任务详情 API
- [ ] 任务事件 API
- [ ] 会话任务列表 API

### P2 Planner

- [ ] `planner.py`
- [ ] 规则模板
- [ ] 工具可用性校验
- [ ] LLM 参数补全
- [ ] 多格漫剧模板
- [ ] 图片/视频/音频/合成模板

### P3 Scheduler / Executor

- [ ] `scheduler.py`
- [ ] `step_executor.py`
- [ ] ready step 计算
- [ ] step 级 prompt
- [ ] step 级工具调用
- [ ] 顺序调度
- [ ] 并行调度

### P4 Auditor

- [ ] `auditor.py`
- [ ] required step 规则
- [ ] artifact verified 规则
- [ ] incomplete/blocked/failed/completed 判定
- [ ] Reporter 分离

### P5 Replanner

- [ ] `replanner.py`
- [ ] retry
- [ ] fallback_tool
- [ ] ask_user
- [ ] skip
- [ ] block
- [ ] fail

### P6 恢复与控制

- [ ] 事件回放
- [ ] 断线恢复
- [ ] cancel
- [ ] retry
- [ ] resume
- [ ] 任务控制前端按钮

### P7 观测

- [ ] trace 记录
- [ ] 事件时间线
- [ ] 工具调用详情
- [ ] 成功率/失败率统计

### P8 LangGraph-like 评估

- [ ] StateGraph 映射
- [ ] demo branch
- [ ] 复杂度对比
- [ ] 是否接入决策

---

## 5. 推荐实施顺序

推荐顺序不是从最酷的功能开始，而是从“状态可靠性”开始：

```text
P0.5 验证
  ↓
P1 持久化
  ↓
P2 Planner
  ↓
P3 Scheduler / StepExecutor
  ↓
P4 Auditor
  ↓
P5 Replanner
  ↓
P6 断线恢复
  ↓
P7 Tracing
  ↓
P8 LangGraph-like 评估
```

原因：

- 没有持久化，就无法恢复和复盘。
- 没有 Planner，就没有真正 TaskGraph。
- 没有 Scheduler，就仍然依赖 LLM 自己决定下一步。
- 没有 Auditor，就会继续误判完成。
- 没有 Replanner，失败恢复仍然不可控。

---

## 6. 风险控制

### 6.1 不要一次性重写 AgentRunner

`agent_runner.py` 当前承担很多兼容逻辑，直接重写风险高。

建议：

```text
先抽 store
再抽 planner
再抽 scheduler
再抽 executor
最后让 agent_runner.py 变成薄入口
```

### 6.2 保持旧事件兼容

必须继续支持：

- `delta`
- `thinking`
- `tool_start`
- `tool_done`
- `tool_confirm`
- `incomplete`
- `done`

新增事件只能增强，不能破坏旧前端逻辑。

### 6.3 数据库迁移风险

当前项目启动使用 `Base.metadata.create_all`，后续建议补 Alembic migration。

P1 可以先用 create_all 继续推进，但生产部署前必须补迁移脚本。

### 6.4 Replanner 防循环

必须有硬约束：

- 每个 step 最大 retry 次数。
- 每个 fallback tool 最大调用次数。
- 总工具调用预算。
- 总任务时长预算。
- 用户拒绝后不得重复调用同一工具。

---

## 7. 最终验收标准

完整 vNext 达标条件：

- [ ] 用户提出复杂多步骤创作任务，后端生成结构化 TaskGraph。
- [ ] 每个 step 有明确状态和依赖。
- [ ] 工具结果统一为 ToolResult。
- [ ] 图片/视频/音频产物统一登记为 AgentArtifact。
- [ ] 任务状态、步骤、产物、事件、工具调用均可持久化查询。
- [ ] 前端只展示后端权威状态，不再靠文本猜测完成度。
- [ ] 工具失败后可 retry/fallback/ask_user/block/fail。
- [ ] 断线后可以恢复任务视图。
- [ ] 最终报告来自后端 Reporter，并明确 completed/failed/blocked/incomplete。
- [ ] 可通过事件时间线复盘完整任务过程。

---

## 8. 一句话结论

当前 P0 已经把漫剧 Agent 从“纯 ReAct 工具循环”推进到“后端状态驱动”的第一步。

后续实施重点是：

```text
先持久化，再任务图，再调度，再审计，再重规划，再恢复和观测。
```

最终目标是让漫剧 Agent 成为：

```text
面向多媒体创作的领域型 LangGraph-like Agent Runtime
```
