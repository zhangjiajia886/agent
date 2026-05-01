# P10 Agent 设计模式选型

> 所属阶段：P10  
> 状态：待实施  
> 目标：系统梳理 ttsapp 漫剧 Agent 应采用、暂缓采用和不建议采用的 Agent 设计模式，并明确每种模式对应的工程模块。

---

## 1. 背景

当前漫剧 Agent 已经从纯 ReAct 工具循环演进到 P0 状态事件闭环，并规划了持久化、Planner、Scheduler、Auditor、Replanner、Sandbox、Budget 等模块。

为了避免后续架构碎片化，需要统一 Agent 设计模式选型。

## 2. 目标

- [ ] 明确当前已采用的设计模式。
- [ ] 明确必须引入的设计模式。
- [ ] 明确暂缓采用的设计模式。
- [ ] 明确每种模式对应的模块和阶段。
- [ ] 明确与 LangChain/LangGraph/CrewAI/AutoGen 等方案的取舍。

## 3. 已采用模式

| 模式 | 当前状态 | 对应模块 |
|---|---|---|
| ReAct | 已采用 | `agent_runner.py` |
| Tool Calling | 已采用 | `tool_executor.py` / ToolRegistry |
| Human-in-the-loop | 已采用 | `tool_confirm` / approval_queue |
| Event-Driven | P0 已采用 | task/step/artifact/final_report 事件 |
| Artifact-Centric | P0 已采用 | ToolResult.artifacts / AgentArtifact |
| State Machine | 初步采用 | AgentTaskStatus / AgentStepStatus |

## 4. 必须引入模式

### 4.1 Plan-and-Execute

```text
Planner → TaskGraph → Executor
```

对应：P2 Planner、P3 Scheduler。

### 4.2 TaskGraph / DAG

```text
step depends_on upstream steps
```

对应：AgentStep.depends_on、Scheduler。

### 4.3 CompletionAuditor

```text
规则判断完成，不信模型自述
```

对应：P4 Auditor。

### 4.4 Replanner / RecoveryPolicy

```text
失败后 retry/fallback/ask_user/block/fail
```

对应：P5 Replanner。

### 4.5 Sandbox Agent

```text
ToolCall → RiskPolicy → SandboxPolicy → Executor
```

对应：P7 沙箱与安全。

### 4.6 Budgeted Agent

```text
工具调用、token、视频生成都有预算
```

对应：P11 成本与预算控制。

### 4.7 Event Sourcing

```text
AgentEvent replay 重建前端状态
```

对应：P6 恢复与观测、P9 状态层。

## 5. 建议引入模式

### 5.1 Observer / Verifier

工具完成后验证产物。

```text
ToolResult
  ↓
Observer 检查文件/URL/大小/格式
  ↓
Artifact.verified
```

建议后续放入 P4 Auditor 或单独 P12。

### 5.2 Memory-Augmented Agent

维护多类记忆：

- ConversationMemory
- TaskMemory
- ArtifactMemory
- FailureMemory
- UserPreferenceMemory

建议后续单独设计。

### 5.3 Critic / Reflection

用于质量检查：

- 图片是否符合 prompt。
- 视频动作是否正确。
- final_report 是否遗漏。

建议后期引入，不作为 P1/P2 前置。

## 6. 暂缓采用模式

### 6.1 Multi-Agent

```text
Director / Visual / Motion / Audio / Auditor
```

暂缓原因：

- 状态层尚未稳定。
- 工具治理和沙箱未实现。
- 成本会显著上升。

### 6.2 全量 LangGraph Runtime

暂缓原因：

- 当前业务对象已经很明确。
- 需要先稳定自研 TaskGraph 数据模型。
- 可后续做实验分支。

### 6.3 全量 LangChain Agent 替换

不建议原因：

- 当前核心问题不是缺 Agent 框架。
- 主要问题是状态、产物、审计、恢复和安全。

## 7. 最终组合架构

```text
User Goal
  ↓
TaskPlanner              # Plan-and-Execute
  ↓
TaskGraph / StateMachine # DAG + State Machine
  ↓
Scheduler                # 调度 ready steps
  ↓
StepExecutor             # ReAct + Tool Calling
  ↓
Sandbox / Budget         # 安全与预算
  ↓
ToolExecutor
  ↓
ToolResult
  ↓
Observer / ArtifactMemory
  ↓
CompletionAuditor
  ↓
Replanner if needed
  ↓
Reporter
  ↓
Event Stream + DB/Redis
```

## 8. 模式与阶段映射

| 阶段 | 模式 |
|---|---|
| P0.5 | Event-Driven / Artifact-Centric |
| P1 | Event Sourcing 基础 / DB State |
| P9 | DB/Redis State Layer |
| P7 | Sandbox Agent |
| P8 | Tool Governance |
| P11 | Budgeted Agent |
| P2 | Plan-and-Execute / TaskGraph |
| P3 | Scheduler / StepExecutor / State Machine |
| P4 | CompletionAuditor / Observer |
| P5 | Replanner / RecoveryPolicy |
| P6 | Event Replay / Tracing |

## 9. TODO

- [ ] 在 README 中加入 P10。
- [ ] 后续实现模块时标注采用的设计模式。
- [ ] P2 Planner 实施前复核 Plan-and-Execute 边界。
- [ ] P3 Scheduler 实施前复核 State Machine 状态转移。
- [ ] P4 Auditor 实施前补 Observer/Verifier 子设计。
- [ ] P5 Replanner 实施前补 RecoveryPolicy 决策表。

## 10. 验收标准

- [ ] 每个核心阶段都能对应至少一种设计模式。
- [ ] 不再用“加 prompt”解决结构性问题。
- [ ] Multi-Agent / LangGraph 等复杂方案有明确暂缓理由。
- [ ] 最终架构图能解释 Agent 从用户目标到最终报告的完整链路。
