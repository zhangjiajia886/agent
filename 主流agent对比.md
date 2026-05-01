# 主流 Agent 对比：基于漫剧 Agent 深度优化设计的评估

> 生成时间：2026 年 5 月  
> 对比对象：`漫剧agent深度优化设计.md` 与 LangChain/LangGraph、CrewAI、AutoGen、OpenAI Assistants、Claude Code/OpenHands、OpenClaw/Workflow Agent 等主流 Agent 架构。  
> 核心目标：判断当前漫剧 Agent vNext 设计是否符合主流 Agent 工程方向，以及哪些能力应该借鉴 LangChain/LangGraph，哪些能力应保持 ttsapp 自研。

---

## 0. 总结结论

`漫剧agent深度优化设计.md` 提出的方向是正确的，它已经从传统 ReAct Agent 进化到接近 LangGraph / Workflow Agent 的工程化形态。

核心变化是：

```text
旧架构：messages → LLM → tools → messages

新设计：TaskGraph → StepExecutor → ToolResult → Auditor → Replanner → FinalReport
```

这与 2026 年主流 Agent 工程趋势高度一致。

### 0.1 与主流框架的总体匹配度

| 对比对象 | 匹配度 | 主要相似点 | 主要差异 |
|---|---:|---|---|
| **LangGraph** | 85% | 显式状态、节点、边、可恢复流程、DAG 思维 | 漫剧设计更偏业务 TaskGraph；LangGraph 是通用状态机框架 |
| **LangChain Agent** | 65% | 工具注册、ReAct、Function Calling、工具执行 | LangChain 传统 Agent 偏链式调用，状态控制弱于当前优化设计 |
| **CrewAI Flow** | 70% | 任务分工、流程编排、角色/步骤拆分 | CrewAI 偏多角色协作；漫剧 Agent 偏单 Agent 多工具执行 |
| **AutoGen** | 60% | 多 Agent 对话、工具调用、反思协作 | AutoGen 偏 Agent 间通信；漫剧 Agent 更需要产物 DAG 和媒体流水线 |
| **OpenAI Assistants / Responses API** | 60% | Thread、Tool、Run、状态管理 | OpenAI 托管较多；漫剧 Agent 需要本地任务图和媒体产物数据库 |
| **Claude Code / OpenHands** | 70% | 工具执行、文件/终端、验证闭环、安全审批 | Claude Code 偏工程代码任务；漫剧 Agent 偏多媒体创作任务 |
| **OpenClaw / Workflow Agent** | 80% | Plan-and-Execute、任务图、执行状态、重规划 | OpenClaw 更偏通用任务自动化；漫剧设计有更强媒体产物链 |

### 0.2 最重要判断

漫剧 Agent vNext 不应该简单“接入 LangChain 就完事”。

更合理路线是：

```text
借鉴 LangGraph 的状态机思想
保留 ttsapp 自己的业务 TaskGraph / ArtifactMemory / ToolResult / 前端工作台
```

原因：

- 漫剧 Agent 的核心价值不在“会调用工具”，而在“可靠完成媒体创作链”。
- LangChain 提供通用抽象，但不会天然理解图片、视频、音频、ComfyUI、即梦、TTS、合成这些业务产物关系。
- ttsapp 已经有工具执行器、前端工作台、ComfyUI/Jimeng/TTS 集成，自研 TaskGraph 更贴合业务。

最终建议：

```text
不要整体迁移到 LangChain Agent。
可以借鉴 LangGraph 的 StateGraph / node / edge / checkpoint 思想。
用 ttsapp 自研 TaskGraph 作为业务状态源。
```

---

## 1. 被评估的漫剧 Agent vNext 设计

`漫剧agent深度优化设计.md` 的核心架构是：

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

它本质上是一个混合架构：

```text
Plan-and-Execute / Workflow Agent
+ ReAct Step Executor
+ ArtifactMemory
+ CompletionAuditor
+ Recovery Policy
+ Frontend Workbench
```

### 1.1 设计的核心优点

- **TaskGraph 权威状态**：解决“任务到底完成没完成”。
- **ToolResult 标准化**：解决工具返回格式混乱。
- **ArtifactMemory**：图片、视频、音频不再只是字符串，而是可追踪产物。
- **CompletionAuditor**：停止判断从关键词升级为任务图审计。
- **Replanner**：失败后可重试、换工具、询问用户。
- **前端展示后端状态**：避免前端自己猜测完成度。
- **DAG 并行能力**：图生视频和 TTS 可以并行。

### 1.2 设计的潜在风险

- 架构复杂度明显上升。
- 数据库表和事件协议增加，迁移成本高。
- Planner 如果过度依赖 LLM，仍可能生成不稳定计划。
- Replanner 如果策略不清晰，可能引入新的循环问题。
- 与现有 `agent_runner.py`、`orchestrator.py`、Workflow DAG 引擎之间需要边界清晰，否则会重复造轮子。

---

## 2. LangChain 体系概览

LangChain 不是单一 Agent 架构，而是一组生态组件。

### 2.1 LangChain 核心组件

```text
LangChain
├── Models / ChatModels
├── PromptTemplate
├── Tools
├── Agents
├── Chains
├── Memory
├── Retrievers
├── OutputParsers
└── Callbacks / Tracing
```

传统 LangChain Agent 的典型模式：

```text
Prompt + Tools + LLM
  ↓
Agent decides action
  ↓
Tool executes
  ↓
Observation appended
  ↓
Agent continues or finishes
```

这与 ReAct Agent 非常接近。

### 2.2 LangChain Agent 的优点

- 工具抽象成熟。
- 接入模型和工具生态快。
- ReAct / OpenAI Function Calling 等范式现成。
- 输出解析器、Prompt 模板、Retriever 组件丰富。
- 与 LangSmith 观测体系结合好。

### 2.3 LangChain Agent 的不足

传统 LangChain Agent 的问题与当前旧版漫剧 Agent 类似：

- 状态经常藏在 messages 中。
- 长任务完成度难判断。
- 工具失败恢复依赖 prompt。
- 复杂 DAG 不自然。
- 业务产物管理需要自己实现。

因此，如果只把漫剧 Agent 改成 LangChain Agent，不能根治问题。

### 2.4 对漫剧 Agent 的启发

可以借鉴：

- Tool 抽象。
- Callback / tracing 思路。
- OutputParser 思路。
- Retriever 和 Memory 组件设计。

不建议直接照搬：

- 传统 AgentExecutor 作为主循环。
- 只依赖 prompt 控制完成判断。
- 把多媒体产物藏在 message history 里。

---

## 3. LangGraph 深度对比

LangGraph 是 LangChain 生态中更适合复杂 Agent 的框架。

它的核心是：

```text
StateGraph = State + Nodes + Edges + Checkpoint
```

典型流程：

```text
State
  ↓
Node A
  ↓
根据条件 Edge 跳转
  ↓
Node B / Node C
  ↓
更新 State
  ↓
Checkpoint
```

### 3.1 LangGraph 与漫剧 Agent vNext 的结构对比

| LangGraph 概念 | 漫剧 Agent vNext 对应设计 | 说明 |
|---|---|---|
| State | AgentTask + AgentStep + AgentArtifact + AgentEvent | 漫剧设计把 State 拆成数据库实体 |
| Node | Planner / StepExecutor / ToolExecutor / Auditor / Replanner | 每个模块都可视为节点 |
| Edge | depends_on / Scheduler / next_action | 漫剧设计用 DAG 和调度规则表达边 |
| Checkpoint | agent_events / task state persistence | 支持断线恢复和事件回放 |
| Conditional Edge | Auditor / Replanner 决策 | success/error/blocked/retry/fallback |
| Tool Node | ToolExecutor | 工具执行节点 |
| Human-in-the-loop | approval_required | 审批事件 |

结论：

> 漫剧 Agent vNext 的思想与 LangGraph 高度接近，只是它采用业务实体建模，而不是直接使用 LangGraph 的 Python StateGraph API。

### 3.2 LangGraph 的优势

#### 1. 状态机表达清晰

LangGraph 把执行流显式写成节点和边：

```text
planner → executor → auditor → reporter
              ↓ error
           replanner
```

这比传统 ReAct 更稳定。

#### 2. Checkpoint 机制成熟

LangGraph 支持中断、恢复、回放。

对漫剧 Agent 来说，这对应：

- WebSocket 断线恢复。
- 长视频任务中断恢复。
- 用户审批后继续执行。
- 失败后从某一步重跑。

#### 3. Human-in-the-loop 自然

LangGraph 可以在某节点等待用户输入，然后恢复。

漫剧 Agent 的工具审批也需要这一点。

#### 4. 条件分支自然

例如：

```text
ToolResult success → Auditor
ToolResult retryable error → Retry
ToolResult fatal error → Failed
ToolResult missing input → AskUser
```

### 3.3 LangGraph 的不足

#### 1. 它是通用框架，不是业务模型

LangGraph 不会天然提供：

- `AgentTask`。
- `AgentStep`。
- `AgentArtifact`。
- 图片/视频/音频产物表。
- ComfyUI/Jimeng/TTS 工具结果标准。
- 前端任务工作台协议。

这些仍然需要 ttsapp 自己实现。

#### 2. 状态如果只放内存或 checkpoint，不利于业务查询

漫剧 Agent 需要：

- 用户查看历史任务。
- 前端刷新恢复。
- 产物图库展示。
- 后台统计任务成功率。
- 失败案例复盘。

这些更适合数据库实体，而不是仅依赖框架 checkpoint。

#### 3. 接入成本与现有架构冲突

当前 ttsapp 已有：

- FastAPI WebSocket。
- DB ToolRegistry。
- 自研 tool_executor。
- ComfyUI/Jimeng/TTS 工具。
- 前端工作台。
- Workflow DAG 引擎。

如果强行整体接入 LangGraph，可能形成两套 DAG：

```text
LangGraph StateGraph
现有 comic_engine DAG / 新 AgentTaskGraph
```

这会增加复杂度。

### 3.4 对 LangGraph 的最佳借鉴方式

建议借鉴思想，而不是立刻全面依赖框架。

```text
借鉴：State / Node / Edge / Checkpoint / Conditional Routing
实现：ttsapp 自研 TaskGraphStore + Scheduler + Auditor
```

也可以在 P2 或 P3 阶段评估局部接入：

- 用 LangGraph 承载 Agent Runtime。
- 但 State 仍映射到 ttsapp 的 `agent_tasks/agent_steps/agent_artifacts`。
- ToolExecutor 仍使用 ttsapp 自研工具层。

---

## 4. LangChain vs LangGraph vs 漫剧 Agent vNext

### 4.1 总体对比

| 维度 | LangChain Agent | LangGraph | 漫剧 Agent vNext |
|---|---|---|---|
| 核心范式 | ReAct / Tool Use | StateGraph / Workflow | TaskGraph + ReAct Step |
| 状态管理 | messages/memory | 显式 State | DB 任务图 + 事件流 |
| 工具调用 | 强 | 强 | 强，且业务工具丰富 |
| DAG 表达 | 弱 | 强 | 强，业务化 DAG |
| 完成判断 | 依赖 Agent 输出 | 可通过状态机 | CompletionAuditor |
| 失败恢复 | prompt/自定义 | 条件边 | Replanner / Recovery Policy |
| 断点恢复 | 需额外实现 | 内建 checkpoint | agent_events + task store |
| 人工审批 | 需额外实现 | 支持中断恢复 | approval_required |
| 业务产物管理 | 需自研 | 需自研 | 原生设计 ArtifactMemory |
| 前端工作台 | 无 | 无 | 原生设计 |

### 4.2 对漫剧 Agent 的结论

- 如果只做简单工具 Agent：LangChain 足够。
- 如果做复杂任务状态机：LangGraph 更适合。
- 如果做漫剧生产系统：必须有自研业务 TaskGraph 和 ArtifactMemory。

因此最佳路线：

```text
基础思想：LangGraph
执行灵活性：ReAct Step Executor
业务状态：ttsapp AgentTaskGraph
工具层：ttsapp ToolExecutor
前端：ttsapp Agent Workbench
```

---

## 5. CrewAI 对比

CrewAI 的核心是“角色 + 任务 + 流程”。

典型结构：

```text
Crew
├── Agent: Planner
├── Agent: Researcher
├── Agent: Writer
├── Agent: Reviewer
└── Tasks / Flow
```

### 5.1 CrewAI 适合什么

- 多角色协作。
- 文案生成。
- 研究报告。
- 市场分析。
- 内容生产流水线。

### 5.2 与漫剧 Agent 对比

| 维度 | CrewAI | 漫剧 Agent vNext |
|---|---|---|
| 核心单位 | Agent 角色 | Task/Step/Artifact |
| 执行方式 | 多 Agent 协作 | 单 Agent Runtime + 多工具 |
| 状态重点 | 任务委派 | 产物链和步骤状态 |
| 适合场景 | 文本/研究/团队协作 | 图片/视频/音频创作链 |
| 工具依赖 | 可接工具 | 强依赖媒体工具 |

### 5.3 可借鉴点

- 角色分工思想：Planner、Director、Artist、Editor、Auditor。
- 任务模板思想：不同漫剧风格对应不同 crew/task template。
- Reviewer 角色：可作为 CompletionAuditor 的 LLM 解释层。

### 5.4 不建议照搬点

不建议把每一步都变成独立 Agent 对话。

原因：

- 成本高。
- 状态同步复杂。
- 媒体产物传递仍要自研。
- 多 Agent 对话不一定比 TaskGraph 更可靠。

---

## 6. AutoGen 对比

AutoGen 的核心是多 Agent 对话协作。

典型结构：

```text
UserProxyAgent
AssistantAgent
ToolAgent
ReviewerAgent
GroupChatManager
```

### 6.1 AutoGen 优点

- 多智能体互相讨论。
- 适合复杂推理和协作式任务。
- 可以让不同 Agent 承担不同职责。
- 对研究、代码生成、方案讨论有价值。

### 6.2 与漫剧 Agent 对比

| 维度 | AutoGen | 漫剧 Agent vNext |
|---|---|---|
| 核心机制 | Agent 间对话 | TaskGraph 调度 |
| 状态权威 | 对话历史 | 数据库任务图 |
| 完成判断 | 对话协议/自定义 | CompletionAuditor |
| 工具执行 | Tool Agent | ToolExecutor |
| 媒体产物 | 需自定义 | ArtifactMemory |
| 适合任务 | 协作推理 | 创作流水线 |

### 6.3 对漫剧 Agent 的启发

可以在后期引入“虚拟角色”：

```text
DirectorAgent：分镜导演
VisualAgent：画面生成
MotionAgent：动态视频
AudioAgent：旁白音频
CriticAgent：验收审计
```

但它们不应直接通过自由聊天传递状态，而应读写同一个 TaskGraph。

即：

```text
Multi-Agent 可以作为执行策略
TaskGraph 必须仍是状态源
```

---

## 7. OpenAI Assistants / Responses API 对比

OpenAI Assistants 类架构通常包含：

```text
Assistant
Thread
Run
Tool Call
Message
File
```

### 7.1 优点

- 托管线程和工具调用状态。
- Function Calling 规范强。
- 文件能力和代码解释器方便。
- API 生态标准化。

### 7.2 与漫剧 Agent 对比

| OpenAI 概念 | 漫剧 Agent vNext 对应 |
|---|---|
| Assistant | AgentPrompt + ModelConfig |
| Thread | AgentConversation |
| Run | AgentTask |
| Run Step | AgentStep / ToolInvocation |
| Tool Call | ToolInvocation |
| File | AgentArtifact |

### 7.3 主要差异

OpenAI Assistants 更像托管 Agent Runtime，而 ttsapp 需要自主管控：

- 多模型供应商。
- ComfyUI 远程 GPU。
- 即梦 API。
- 本地上传文件。
- 前端任务工作台。
- 自定义审批策略。
- 自定义失败恢复。

因此 ttsapp 不适合把核心状态完全托管给 OpenAI。

### 7.4 可借鉴点

- Run / Run Step 概念。
- Tool Call 生命周期。
- Thread 消息与任务执行分离。
- 文件作为一等对象。

---

## 8. Claude Code / OpenHands / Computer-Use Agent 对比

Claude Code、OpenHands、Cursor Agent、Windsurf Cascade 代表 Computer-Use / Coding Workspace Agent。

它们的典型闭环：

```text
理解需求
  ↓
搜索文件
  ↓
读取代码
  ↓
修改代码
  ↓
运行测试
  ↓
读取日志
  ↓
修复错误
  ↓
总结交付
```

### 8.1 与漫剧 Agent 的共同点

漫剧 Agent 已经有通用工具：

- `bash`
- `read_file`
- `write_file`
- `edit_file`
- `python_exec`
- `grep_search`
- `find_files`
- `http_request`

这些是 Computer-Use Agent 的基础。

### 8.2 关键差异

| 维度 | Claude Code/OpenHands | 漫剧 Agent vNext |
|---|---|---|
| 任务对象 | 代码库 | 多媒体创作链 |
| 产物 | 代码 diff / 测试结果 | 图片 / 视频 / 音频 / 合成文件 |
| 验证方式 | 单测/构建/日志 | 文件存在/可下载/可播放/满足用户目标 |
| 状态源 | 工作区 + 工具轨迹 | TaskGraph + ArtifactMemory |
| 风险 | 文件破坏/命令风险 | 媒体成本/GPU任务/文件和命令风险 |

### 8.3 可借鉴点

- 工具调用前说明意图。
- 高风险操作审批。
- 执行后验证。
- 出错读日志再修复。
- 最终总结列出修改/产物/验证结果。

### 8.4 漫剧 Agent 应增加的 Computer-Use 能力

- ComfyUI 任务失败后自动读取错误详情。
- 产物生成后自动验证文件大小、类型、可访问性。
- TTS 输出后检查音频大小和格式。
- 视频输出后检查文件是否存在、大小是否合理。
- 工具失败必须形成 step error，而不是只写入聊天文本。

---

## 9. OpenClaw / Workflow Agent 对比

OpenClaw 类系统强调：

```text
任务理解 → 任务树 → 执行器 → 观察器 → 反思器 → 重规划 → 报告
```

这与 `漫剧agent深度优化设计.md` 最接近。

### 9.1 相似点

- 都强调 TaskGraph。
- 都强调执行状态。
- 都强调失败恢复。
- 都强调最终报告不能胡说完成。
- 都不把 Agent 简化为一次 LLM 调用。

### 9.2 差异点

| 维度 | OpenClaw / Workflow Agent | 漫剧 Agent vNext |
|---|---|---|
| 任务类型 | 通用自动化 | 漫剧/多媒体创作 |
| 产物类型 | 文件/网页/任务结果 | image/video/audio/file |
| 调度 | 通用任务图 | 媒体依赖 DAG |
| 工具 | 浏览器/API/文件 | ComfyUI/Jimeng/TTS/媒体合成/通用工具 |
| 前端 | 任务流展示 | 创作工作台 + 产物图库 |

### 9.3 结论

漫剧 Agent vNext 可以理解为：

```text
面向多媒体创作领域的 OpenClaw-like Workflow Agent
```

其重点不是通用性最大化，而是媒体创作可靠性最大化。

---

## 10. 主流框架能力矩阵

| 能力 | LangChain Agent | LangGraph | CrewAI | AutoGen | OpenAI Assistants | Claude Code/OpenHands | 漫剧 Agent vNext |
|---|---:|---:|---:|---:|---:|---:|---:|
| ReAct 工具调用 | 强 | 强 | 中 | 中 | 强 | 强 | 强 |
| 显式任务图 | 弱 | 强 | 中 | 弱 | 中 | 中 | 强 |
| DAG 调度 | 弱 | 强 | 中 | 弱 | 弱 | 中 | 强 |
| 状态持久化 | 中 | 强 | 中 | 中 | 强 | 中 | 强 |
| Human-in-loop | 中 | 强 | 中 | 中 | 强 | 强 | 强 |
| 工具失败恢复 | 中 | 强 | 中 | 中 | 中 | 强 | 强 |
| 多 Agent 协作 | 弱 | 可实现 | 强 | 强 | 弱 | 中 | 可扩展 |
| 多媒体产物管理 | 弱 | 需自研 | 弱 | 弱 | 中 | 弱 | 强 |
| 前端任务工作台 | 无 | 无 | 无 | 无 | 无 | 部分产品有 | 强 |
| 业务定制性 | 中 | 高 | 中 | 中 | 中 | 中 | 高 |

---

## 11. 对漫剧 Agent 深度优化设计的评价

### 11.1 先进性评价

`漫剧agent深度优化设计.md` 的设计在方向上是先进的。

它没有停留在：

```text
给 LLM 更多 prompt
让 LLM 自己更努力地调用工具
```

而是转向：

```text
用系统架构约束 Agent 行为
用 TaskGraph 管理任务
用 ToolResult 管理观察
用 Auditor 管理完成判断
用 Replanner 管理失败恢复
```

这正是主流 Agent 从 demo 走向 production 的关键路径。

### 11.2 相比 LangChain 的优势

- 更适合长任务。
- 更适合多媒体创作链。
- 有明确 ArtifactMemory。
- 有后端权威 TaskGraph。
- 有前端工作台协议。
- 更容易做业务审计和历史任务查询。

### 11.3 相比 LangChain 的不足

- 生态组件少，需要自研更多。
- PromptTemplate、Tool、Callback、Tracing 等基础设施不如 LangChain 成熟。
- 缺少 LangSmith 类统一观测平台。
- 多模型适配、输出解析、工具 schema 管理需要继续增强。

### 11.4 相比 LangGraph 的优势

- 业务实体更清晰。
- 与现有 FastAPI/MySQL/前端工作台更贴合。
- 媒体产物链是一等公民。
- 不受框架抽象限制。

### 11.5 相比 LangGraph 的不足

- 需要自己实现状态机调度。
- 需要自己实现 checkpoint 和恢复。
- 需要自己处理条件边和中断恢复。
- 实现质量取决于工程纪律。

---

## 12. 是否应该引入 LangChain / LangGraph

### 12.1 不建议：整体替换为 LangChain Agent

原因：

- 不能解决 TaskGraph 和 ArtifactMemory 根问题。
- 当前问题不是“没有 Agent 框架”，而是“没有权威任务状态”。
- 迁移成本高，收益有限。

### 12.2 可以考虑：局部使用 LangChain 组件

可用部分：

- PromptTemplate。
- OutputParser。
- Tool schema helper。
- Retriever/RAG 组件。
- LangSmith tracing 思路。

### 12.3 可以考虑：参考或局部接入 LangGraph

两种路线：

#### 路线 A：自研 TaskGraph，借鉴 LangGraph 思想

```text
优点：最贴合业务，迁移风险低
缺点：调度器、checkpoint 需要自研
```

推荐当前采用。

#### 路线 B：用 LangGraph 承载 Runtime，ttsapp DB 承载业务状态

```text
LangGraph StateGraph
  ↓
每个 node 读写 ttsapp agent_tasks/steps/artifacts
  ↓
ToolExecutor 仍用 ttsapp 自研
```

适合 P2/P3 阶段验证。

#### 路线 C：完全迁移到 LangGraph

不建议当前阶段执行。

原因：

- 会与现有 Workflow DAG 引擎重叠。
- 会增加调试复杂度。
- 媒体产物管理仍需自研。

---

## 13. 漫剧 Agent vNext 推荐架构定位

最终定位：

```text
领域型 Workflow Agent
```

不是：

```text
通用 LangChain Agent
```

也不是：

```text
纯多 Agent 聊天系统
```

而是：

```text
面向漫剧/短视频/数字人创作的 TaskGraph Agent
```

其核心资产是：

```text
任务图 + 媒体产物图 + 工具执行图 + 前端工作台
```

### 13.1 最佳混合架构

```text
业务层：ttsapp AgentTaskGraph
状态层：MySQL agent_tasks / agent_steps / agent_artifacts / agent_events
执行层：ReActStepExecutor
工具层：ttsapp ToolExecutor + ToolResult
调度层：TaskScheduler / Replanner
审计层：CompletionAuditor
前端层：ComicAgent Workbench
可选框架思想：LangGraph State/Node/Edge/Checkpoint
```

### 13.2 未来可选增强

- 引入 LangSmith 类 tracing。
- 用 LangGraph 做实验性 runtime。
- 用 CrewAI 思想增加 Director/Artist/Auditor 角色。
- 用 AutoGen 思想做多 Agent 分镜讨论。
- 用 Computer-Use 思想增强验证闭环。

---

## 14. 分阶段建议

### P0：不要引入重框架，先完成自研状态底座

优先：

- `agent_tasks`
- `agent_steps`
- `agent_artifacts`
- `agent_events`
- `tool_invocations`
- `ToolResult`
- `CompletionAuditor`

理由：

> 没有业务状态底座，引入任何 Agent 框架都会变成“另一个更复杂的 messages 循环”。

### P1：实现 TaskScheduler / Replanner

优先：

- DAG depends_on。
- ready step 调度。
- retry/fallback/block。
- step-level ReAct。

### P2：补强可观测性

可以借鉴 LangSmith：

- 每轮 LLM 调用记录。
- 每次工具调用记录。
- 每个 step 状态变化记录。
- 每个失败原因分类。
- 任务回放。

### P3：评估 LangGraph 局部接入

只有在自研状态模型稳定后，再评估：

```text
是否用 LangGraph 替换 TaskScheduler / Runtime loop
```

不要在 P0 直接引入，避免把状态边界搞复杂。

---

## 15. 最终结论

`漫剧agent深度优化设计.md` 的方向与主流 Agent 演进方向一致，尤其接近 LangGraph / Workflow Agent 的架构思想。

最重要的设计判断是正确的：

```text
Agent 可靠性的核心不是 prompt，而是状态。
```

对 ttsapp 来说，最应该建设的是：

```text
TaskGraph + ArtifactMemory + ToolResult + CompletionAuditor + Replanner
```

LangChain 可以作为工具箱参考，LangGraph 可以作为状态机思想参考，但 ttsapp 漫剧 Agent 不应简单替换成通用框架。

最终推荐路线：

```text
P0：自研业务状态底座
P1：实现 DAG 调度和失败恢复
P2：增强 tracing / checkpoint / 断线恢复
P3：评估 LangGraph 局部接入
```

一句话总结：

> 漫剧 Agent vNext 应该成为“面向多媒体创作的领域型 LangGraph-like Agent”，而不是“套一层 LangChain 的普通工具 Agent”。
