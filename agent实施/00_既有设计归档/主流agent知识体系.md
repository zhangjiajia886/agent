# 主流 Agent 知识体系

> 时间基准：2026 年 4 月  
> 目标：先建立整体地图，再逐层细分学习 OpenClaw、Claude Code、Manus/OpenHands/Cursor/Windsurf 等主流 Agent 设计思想，并沉淀到 ttsapp 漫剧 Agent 的架构优化中。

---

## 0. 先给结论：2026 年主流 Agent 的 3 种设计模式

截至 2026 年 4 月，主流 Agent 大体可以归为 3 类：

| 模式 | 代表产品/框架 | 核心思想 | 适合场景 | 主要风险 |
|---|---|---|---|---|
| **模式一：ReAct Tool-Use Agent** | Claude Code、OpenAI Assistants、早期 LangChain Agent、当前 ttsapp 漫剧 Agent | LLM 在循环中思考、选择工具、观察结果、继续下一步 | 工具调用、代码修改、搜索、生成、多步任务 | 容易空转、重复调用、完成检测困难 |
| **模式二：Plan-and-Execute / Workflow Agent** | OpenClaw、Manus、AutoGPT 新式任务图、CrewAI Flow、n8n AI Flow | 先把目标拆成结构化计划，再由执行器逐步完成 | 长任务、业务流程、内容生产流水线、自动化运营 | 计划僵化，遇到异常需要重规划 |
| **模式三：Computer-Use / Coding Workspace Agent** | Claude Code、OpenHands、Cursor Agent、Windsurf Cascade、Devin 类系统 | Agent 直接操作文件、终端、浏览器、测试环境，形成“软件工程闭环” | 编程、调试、部署、端到端工程任务 | 权限、安全、状态同步、成本和长上下文管理 |

这三种不是互斥关系。成熟 Agent 往往是混合架构：

```text
用户目标
  ↓
任务理解 / 意图分类
  ↓
结构化任务树 Planner
  ↓
ReAct 执行循环 Executor
  ↓
工具 / 浏览器 / 文件 / 终端 / API
  ↓
Observation 结果审计
  ↓
完成判断 / 重规划 / 失败恢复
  ↓
最终报告
```

---

## 1. Agent 的基础概念地图

### 1.1 Agent 和普通 Chatbot 的区别

普通 Chatbot 主要是：

```text
用户输入 → LLM 回复
```

Agent 是：

```text
用户目标 → 理解目标 → 拆任务 → 调工具 → 观察结果 → 修正计划 → 继续执行 → 完成报告
```

关键区别：

- **目标导向**：不是回答一句话，而是完成一个任务。
- **可行动**：可以调用工具、访问文件、执行代码、请求 API。
- **有状态**：维护任务进度、产物、错误、上下文。
- **能反思**：工具返回后判断是否成功，下一步该做什么。
- **能停止**：知道什么时候完成，什么时候失败，什么时候需要用户介入。

### 1.2 一个完整 Agent 的核心模块

```text
Agent
├── Intent Router        意图识别：聊天/工具任务/创作任务/危险操作
├── Planner              任务拆分：目标 → 子任务 / DAG / TODO
├── Executor             执行器：选择工具并调用
├── Tool Registry        工具注册表：工具 schema、权限、描述、风险等级
├── Memory               记忆：会话历史、工作记忆、长期知识、产物路径
├── Observer             观察器：解析工具结果、成功/失败/产物
├── Reflector / Critic   反思器：判断结果是否满足目标
├── Recovery             失败恢复：重试、降级、换工具、询问用户
├── Stop Controller      停止控制：完成/失败/等待用户/超限
└── Reporter             总结报告：完成内容、产物、未完成原因、下一步建议
```

### 1.3 Agent 最容易出问题的地方

| 问题 | 本质原因 |
|---|---|
| 只输出计划，不调用工具 | Planner 和 Executor 没分清；LLM 以为“说计划”就是执行 |
| 工具执行后卡住 | Observation 后没有稳定的下一步决策机制 |
| 明明没完成却显示完成 | Stop Controller 缺失或前端状态兜底错误 |
| 明明完成却继续重复工具 | 完成检测过度依赖关键词，或强制 tool_choice 过度 |
| 用户拒绝后继续重试 | 缺少 rejection memory 和 policy |
| “继续”时忘记上一张图 | 工作记忆没有保留关键产物路径 |
| 工具失败后胡乱猜测 | 工具错误结构不清晰，Agent 没有 recovery policy |
| 多步任务变成多轮用户催促 | 没有任务树和自动续行机制 |

---

## 2. 模式一：ReAct Tool-Use Agent

### 2.1 核心思想

ReAct = Reasoning + Acting。

典型循环：

```text
Thought: 我需要做什么？
Action: 调用某个工具
Observation: 工具返回什么？
Thought: 结果是否满足？下一步是什么？
Action: 再调用工具或结束
```

在 Function Calling 模式下通常表现为：

```text
messages + tools → LLM
  ├── 返回文本：thinking / answer
  └── 返回 tool_calls：执行工具
工具结果 append 到 messages
继续下一轮
```

### 2.2 优点

- 灵活，适合开放式任务。
- 易接入工具 schema。
- 与 OpenAI / Anthropic / Claude / Kimi 等模型接口兼容。
- 适合代码、搜索、图像、音频、文件操作等混合任务。

### 2.3 缺点

- 不稳定，容易空转。
- 容易只写计划不执行。
- 停止条件难设计。
- 复杂任务中状态容易丢。
- 依赖模型是否“自觉”继续工具调用。

### 2.4 ReAct Agent 的正确状态机

不推荐简单写成：

```text
无工具调用 → 结束
```

也不推荐写成：

```text
无工具调用 → 强制调用工具
```

更合理的是：

```text
LLM 返回
├── 有 tool_calls
│   ├── 执行工具
│   ├── 记录 observation
│   ├── 更新工作记忆
│   └── 进入下一轮反思
│
└── 无 tool_calls
    ├── 判断是否是最终报告
    │   ├── 是：结束
    │   └── 否：进入审计
    │
    └── 审计结果
        ├── 任务已完成：总结结束
        ├── 任务未完成但下一步明确：继续下一轮，让模型自主选择工具
        ├── 任务未完成但工具缺失：报告未完成原因
        ├── 模型/API失败：标记失败，允许换模型/重试
        └── 超过迭代预算：生成部分完成报告
```

### 2.5 工具为空时的反思模板

当一轮没有工具调用时，Agent 不应立刻结束。应注入一次审计提示：

```text
[系统审计]
你本轮没有返回工具调用。请基于以下内容判断任务是否彻底完成：
1. 用户原始需求是什么？
2. 已执行哪些工具？分别成功/失败了吗？
3. 已产出哪些文件、图片、视频、音频？
4. 用户要求的每个子任务是否都有对应产物？
5. 如果全部完成：输出最终报告，不要调用工具。
6. 如果未完成：列出剩余 TODO，并自主决定下一步是否需要工具。
7. 如果需要工具但当前没有可用工具：明确说明阻塞原因。
```

关键点：

- 空工具不是完成信号。
- 空工具也不是强制工具信号。
- 空工具是“需要审计”的信号。

---

## 3. 模式二：Plan-and-Execute / Workflow Agent

### 3.1 核心思想

先规划，再执行。

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

### 3.2 任务树结构

复杂任务不应只存在自然语言里，应该变成结构化状态：

```json
{
  "goal": "生成图片→转视频→配旁白",
  "steps": [
    {
      "id": "step_1",
      "title": "生成仙侠退婚宴会图片",
      "tool": "generate_image",
      "status": "pending",
      "inputs": {"prompt": "..."},
      "outputs": {}
    },
    {
      "id": "step_2",
      "title": "图片转动态视频",
      "tool": "image_to_video",
      "status": "blocked",
      "depends_on": ["step_1"],
      "inputs": {"image_path": "${step_1.image_path}"},
      "outputs": {}
    },
    {
      "id": "step_3",
      "title": "生成旁白音频",
      "tool": "text_to_speech",
      "status": "pending",
      "inputs": {"text": "三年之约已到，今日退婚！"},
      "outputs": {}
    }
  ]
}
```

### 3.3 状态枚举

建议每个 step 有明确状态：

| 状态 | 含义 |
|---|---|
| `pending` | 等待执行 |
| `ready` | 依赖已满足，可执行 |
| `running` | 正在执行 |
| `succeeded` | 成功完成，有结果 |
| `failed` | 执行失败 |
| `blocked` | 缺输入、缺工具、等待用户或依赖失败 |
| `skipped` | 被用户取消或不再需要 |

### 3.4 Plan-and-Execute 的优点

- 复杂任务清晰。
- 前端可以稳定展示进度。
- 不依赖 LLM 在自然语言里“记住 TODO”。
- 失败后可以定位具体 step。
- 适合工作流产品和生产系统。

### 3.5 缺点

- 初始设计复杂。
- Planner 生成的计划可能不现实。
- 执行中必须支持重规划。
- 如果过度刚性，会不如 ReAct 灵活。

### 3.6 OpenClaw 类系统的设计启发

OpenClaw 这类 Agent/自动化系统通常强调：

- 任务拆分。
- 多工具编排。
- 可观测执行轨迹。
- 中间状态持久化。
- 面向复杂任务的 Planner + Executor 分离。

可以抽象为：

```text
OpenClaw-like Agent
├── Task Planner       生成任务图
├── Tool Planner       为每步选择工具
├── Executor           执行每步
├── Verifier           校验结果
├── Replanner          失败或偏离时重规划
└── State Store        保存任务状态和产物
```

学习重点不是某个项目的 API，而是它背后的思想：

> 复杂任务不能只靠“下一轮 LLM 自己想起来”，必须有显式任务状态。

---

## 4. 模式三：Computer-Use / Coding Workspace Agent

### 4.1 核心思想

Agent 不只是调用 API，而是像开发者一样操作工作区：

- 读文件
- 搜索代码
- 修改代码
- 运行测试
- 查看日志
- 启动服务
- 调浏览器
- 生成报告
- 反复验证

典型代表：

- Claude Code
- Cursor Agent
- Windsurf Cascade
- OpenHands
- Devin 类系统

### 4.2 Claude Code 的关键思想

Claude Code 这类 Coding Agent 的重点不是“聊天”，而是“工程闭环”：

```text
理解需求
  ↓
搜索代码
  ↓
定位相关文件
  ↓
形成修改计划
  ↓
编辑代码
  ↓
运行测试/构建
  ↓
读日志
  ↓
修复错误
  ↓
总结变更
```

它的核心能力：

- **Repo Awareness**：理解项目结构。
- **Tool Discipline**：先读文件再改，先搜索再动手。
- **Patch-based Editing**：可控修改，不整文件重写。
- **Test Loop**：修改后运行测试。
- **Stateful Work**：记住已改文件、当前问题、失败原因。
- **Safety Policy**：危险命令需要确认。

### 4.3 Workspace Agent 的架构

```text
Coding Agent
├── Repository Indexer       代码库索引
├── Semantic Search          语义搜索
├── File Reader              文件读取
├── Editor                   补丁编辑器
├── Terminal Runner          命令执行
├── Test Runner              测试/构建
├── Log Reader               日志读取
├── Browser Controller       浏览器/页面测试
├── Memory                   项目长期记忆
└── Safety Controller        权限和风险控制
```

### 4.4 对 ttsapp 的启发

漫剧 Agent 不是纯 Coding Agent，但可以借鉴其工程闭环：

```text
创作任务
  ↓
理解需求
  ↓
拆分创作步骤
  ↓
调用图像/视频/音频工具
  ↓
检查产物是否存在
  ↓
记录产物路径
  ↓
如果失败，读取错误并重试/降级
  ↓
如果全部完成，输出报告
```

也就是说，创作 Agent 需要“产物闭环”，类似 Coding Agent 的“测试闭环”。

---

## 5. 三种模式的对比

| 维度 | ReAct | Plan-and-Execute | Computer-Use |
|---|---|---|---|
| 规划方式 | 隐式/即时 | 显式任务树 | 显式+环境探索 |
| 执行方式 | LLM 每轮选工具 | Executor 按步骤执行 | 读写文件/命令/浏览器闭环 |
| 状态管理 | messages 为主 | Task state 为主 | Workspace + memory |
| 适合任务 | 中短开放任务 | 长流程任务 | 软件工程/复杂环境任务 |
| 停止判断 | 难 | 较清晰 | 依赖测试/目标验证 |
| 主要风险 | 空转/重复 | 计划僵化 | 权限/安全/成本 |
| ttsapp 应用 | 工具调用循环 | 漫剧创作流水线 | 日志、文件、测试、部署辅助 |

---

## 6. 复杂任务应该如何拆分

### 6.1 先按“产物链”拆分

用户说：

```text
生成一张仙侠退婚宴会图片，然后转成动态视频，最后配旁白。
```

不要只拆成文字计划，而要拆成产物依赖链：

```text
Step 1: 生成图片
  output: image_path / image_url

Step 2: 图片转视频
  input: Step 1 image_path
  output: video_path / video_url

Step 3: 生成旁白音频
  input: narration text
  output: audio_path / audio_url

Step 4: 合成视频和旁白，可选
  input: Step 2 video + Step 3 audio
  output: final_video
```

### 6.2 再按“工具能力”映射

```text
生成图片 → generate_image / jimeng_generate_image
图片转视频 → image_to_video / jimeng_generate_video
旁白音频 → text_to_speech
音视频合成 → merge_media
```

### 6.3 再按“依赖关系”排序

```text
image_to_video 依赖 image_path
merge_media 依赖 video_path + audio_path
text_to_speech 不依赖图片，可与 image_to_video 并行
```

可优化为：

```text
Step 1: generate_image
Step 2A: image_to_video(image)
Step 2B: text_to_speech(text)
Step 3: merge_media(video, audio)
```

### 6.4 每一步都必须有验收条件

| Step | 成功条件 | 失败条件 |
|---|---|---|
| 生成图片 | 返回 image_url/image_path，文件可访问 | 无 URL、工具 error、文件不存在 |
| 图生视频 | 返回 video_url/video_path，文件可播放 | 超时、ComfyUI 失败、无视频结果 |
| 生成音频 | 返回 audio_url/audio_path，文件可播放 | TTS error、空错误、无音频 |
| 合成 | 返回 final_video | 输入缺失、ffmpeg/工具失败 |

---

## 7. 返回工具为空时，Agent 应如何反思

### 7.1 空工具的 5 种语义

LLM 没有返回工具调用，可能有 5 种含义：

| 类型 | 示例 | 应对 |
|---|---|---|
| 真完成 | “图片和视频都已生成，最终结果如下” | 总结结束 |
| 只写计划 | “我先生成图片，再生成视频” | 审计后继续执行 |
| 中间分析 | “图片已生成，接下来要转视频” | 继续下一步 |
| 阻塞 | “缺少输入图片/工具不可用/API 403” | 标记 blocked/failed |
| 模型异常 | 空回复、API 403、工具 schema 丢失 | 标记 error，允许换模型/重试 |

### 7.2 反思审计结构

空工具时，不应只用正则判断。应该让 Agent 生成结构化审计：

```json
{
  "is_task_complete": false,
  "completed_steps": ["生成图片"],
  "remaining_steps": ["图片转视频", "生成旁白", "合成音视频"],
  "next_action_type": "tool_call",
  "next_tool": "image_to_video",
  "blocking_reason": null,
  "final_report": null
}
```

如果完成：

```json
{
  "is_task_complete": true,
  "completed_steps": ["生成图片", "图片转视频", "生成旁白"],
  "remaining_steps": [],
  "next_action_type": "final_report",
  "next_tool": null,
  "blocking_reason": null,
  "final_report": "本次任务已完成..."
}
```

如果失败：

```json
{
  "is_task_complete": false,
  "completed_steps": ["生成图片"],
  "remaining_steps": ["图片转视频", "生成旁白"],
  "next_action_type": "blocked",
  "next_tool": null,
  "blocking_reason": "LLM API 403，无法继续规划；image_to_video 未被调用",
  "final_report": "任务未完成..."
}
```

### 7.3 空工具处理状态机

```text
NoToolReturned
  ↓
Run Completion Audit
  ↓
AuditResult
  ├── COMPLETE
  │   └── FinalReport → Done
  │
  ├── INCOMPLETE_WITH_NEXT_TOOL
  │   └── ContinueLoop → LLM 自主调用工具
  │
  ├── INCOMPLETE_BUT_BLOCKED
  │   └── IncompleteReport → Stop as blocked
  │
  ├── MODEL_ERROR
  │   └── RetryModel / FallbackModel / Fail
  │
  └── UNCERTAIN
      └── AskUser / Generate Clarifying Question
```

### 7.4 关键原则

- **不能因为空工具直接完成。**
- **不能因为空工具强制调用任意工具。**
- **必须先做完成度审计。**
- **审计应基于结构化任务状态，而不是只看自然语言。**
- **如果审计后仍说“剩余 TODO”，却仍无工具调用，应标记 incomplete，而不是 completed。**

---

## 8. Claude Code / OpenClaw / Manus / OpenHands 的学习重点

### 8.1 Claude Code

重点学习：

- 工程任务如何拆分。
- 先搜索再修改。
- 文件上下文如何最小化读取。
- 工具调用如何安全审批。
- 修改后如何测试。
- 如何输出变更摘要。

对应到 ttsapp：

- Agent 修改代码/部署/测试时，应采用 Claude Code 式工程闭环。
- 创作任务也应借鉴“验证产物”思想。

### 8.2 OpenClaw

重点学习：

- Planner / Executor / Verifier 分层。
- 长任务状态持久化。
- 多工具编排。
- 任务图和可观测执行轨迹。
- 失败后的重规划。

对应到 ttsapp：

- 多步骤漫剧生成应从 ReAct 升级为任务图。
- 每一步必须持久化 status、input、output、error。

### 8.3 Manus / Devin 类 Agent

重点学习：

- 长周期自主任务。
- 浏览器、终端、文件系统联合操作。
- 环境状态观察。
- 自动恢复和验证。
- 端到端交付物。

对应到 ttsapp：

- 自动化生成一套短剧素材时，应像 Devin 一样维护完整任务进度。
- 不能靠用户不断输入“继续”。

### 8.4 OpenHands

重点学习：

- 开源 Coding Agent 的沙箱设计。
- Action/Observation 事件流。
- 多工具统一抽象。
- 终端和文件系统安全控制。

对应到 ttsapp：

- 通用工具如 bash/read_file/write_file/python_exec 应纳入统一风险等级。

### 8.5 Cursor / Windsurf

重点学习：

- IDE 内 Agent 的上下文管理。
- 多文件修改的 plan。
- 实时用户交互。
- 命令执行审批。
- 修改后的验证闭环。

对应到 ttsapp：

- 前端 Agent UI 应清晰展示：当前步骤、工具调用、产物、失败原因、下一步。

---

## 9. ttsapp 漫剧 Agent 推荐核心设计

### 9.1 推荐混合架构

```text
ComicAgent vNext
├── IntentClassifier
│   ├── chat
│   ├── single_tool_task
│   ├── multi_step_creative_task
│   ├── coding_task
│   └── ambiguous_task
│
├── TaskPlanner
│   └── user_goal → TaskGraph
│
├── ReActExecutor
│   ├── choose_next_step
│   ├── call_tool
│   ├── observe_result
│   └── update_task_graph
│
├── CompletionAuditor
│   ├── compare_goal_vs_steps
│   ├── detect_remaining_todo
│   ├── detect_blocker
│   └── decide_stop_or_continue
│
├── ArtifactMemory
│   ├── image_urls
│   ├── video_urls
│   ├── audio_urls
│   ├── file_paths
│   └── step_outputs
│
└── Reporter
    ├── completed_report
    ├── partial_report
    └── failure_report
```

### 9.2 数据结构建议

```python
class AgentTask:
    id: str
    user_goal: str
    status: Literal["running", "completed", "failed", "blocked", "canceled"]
    steps: list[AgentStep]
    artifacts: list[Artifact]
    current_step_id: str | None
    error: str | None

class AgentStep:
    id: str
    title: str
    tool: str | None
    status: Literal["pending", "ready", "running", "succeeded", "failed", "blocked", "skipped"]
    depends_on: list[str]
    inputs: dict
    outputs: dict
    error: str | None
    retry_count: int

class Artifact:
    type: Literal["image", "video", "audio", "file"]
    url: str
    path: str | None
    from_step_id: str
```

### 9.3 Agent 主循环伪代码

```python
while iteration < max_iterations:
    inject_task_state(task)
    response = llm(messages, tools)

    if response.tool_calls:
        for call in response.tool_calls:
            step = match_or_create_step(call)
            mark_running(step)
            result = execute_tool(call)
            observation = normalize_result(result)
            update_step(step, observation)
            update_artifact_memory(observation)
        continue

    audit = completion_auditor(
        user_goal=task.user_goal,
        task_state=task,
        last_text=response.text,
        artifacts=artifact_memory,
    )

    if audit.is_complete:
        task.status = "completed"
        yield final_report(audit)
        break

    if audit.is_blocked:
        task.status = "blocked"
        yield incomplete_report(audit)
        break

    if audit.next_step:
        append_audit_instruction(audit)
        continue

    task.status = "failed"
    yield failure_report(audit)
    break
```

### 9.4 前端状态原则

前端不能仅凭 `done` 标 completed。

应以服务端明确状态为准：

```text
event.type = done + metadata.status = completed → completed
event.type = incomplete → failed/blocked
event.type = error → failed
event.type = tool_done + success → step completed
event.type = tool_done + error → step failed
event.type = tool_confirm → awaiting_approval
```

推荐 done 事件改成：

```json
{
  "type": "done",
  "status": "completed",
  "metadata": {
    "total_tool_calls": 3,
    "completed_steps": 3,
    "remaining_steps": 0,
    "artifacts": ["/uploads/..."]
  }
}
```

如果未完成：

```json
{
  "type": "incomplete",
  "status": "blocked",
  "remaining_steps": ["图片转视频", "生成旁白"],
  "reason": "模型没有返回下一步工具调用"
}
```

---

## 10. 学习路线：先整体，再细分

### 第一阶段：建立 Agent 总体观

学习目标：知道 Agent 是什么、由哪些模块组成。

关键词：

- Agent Loop
- Tool Calling
- Function Calling
- ReAct
- Planner
- Executor
- Memory
- Reflection
- Completion Detection

输出物：

- 画出一个 Agent 总架构图。
- 能解释一次工具调用从 LLM 到执行器再到 Observation 的流程。

### 第二阶段：学习 ReAct Agent

学习目标：理解当前 ttsapp Agent 的核心问题。

重点：

- tool_calls 如何生成。
- 工具结果如何回填 messages。
- 为什么会空工具。
- 为什么会重复调用。
- 如何做 no-tool audit。

输出物：

- 写一个最小 ReAct Agent demo。
- 写出无工具返回时的状态机。

### 第三阶段：学习 Plan-and-Execute

学习目标：复杂任务必须结构化。

重点：

- TaskGraph。
- Step status。
- Dependency。
- Replanner。
- Verifier。

输出物：

- 把“图片→视频→配音”转成结构化 JSON 任务树。
- 给每个 step 定义成功条件和失败条件。

### 第四阶段：学习 Coding Agent

学习目标：掌握 Claude Code / Cursor / Windsurf 的工程闭环。

重点：

- 搜索代码。
- 读文件。
- 修改。
- 测试。
- 日志。
- 总结。

输出物：

- 对 ttsapp 的某个 bug 执行完整闭环分析。

### 第五阶段：落地到 ttsapp

学习目标：把理论变成系统。

优先级：

1. 后端 AgentTask/AgentStep 状态模型。
2. CompletionAuditor。
3. ArtifactMemory。
4. done/incomplete/error 事件协议。
5. 前端按真实状态展示。
6. 自动化测试覆盖多步任务。

---

## 11. 推荐阅读与研究清单

### 必学概念

- ReAct: Reasoning and Acting
- Tool Calling / Function Calling
- Plan-and-Execute Agent
- Reflexion / Self-Reflection
- Tree of Thoughts / Graph of Thoughts
- Memory-Augmented Agent
- Multi-Agent Collaboration
- Computer Use Agent
- Agent Evaluation

### 推荐研究对象

| 对象 | 学什么 |
|---|---|
| Claude Code | 工程闭环、工具纪律、代码库上下文 |
| OpenClaw | 任务拆分、工具编排、任务状态 |
| OpenHands | 开源 Coding Agent、Action/Observation |
| Cursor Agent | IDE Agent 交互和多文件修改 |
| Windsurf Cascade | 计划、工具、用户同步、长期上下文 |
| Manus / Devin 类 | 长任务、自主执行、环境操作 |
| LangGraph | 显式状态机和图式 Agent |
| CrewAI Flow | 多角色与流程编排 |
| AutoGen | 多 Agent 通信与协作 |

---

## 12. 对当前 ttsapp 的结论

当前 ttsapp 漫剧 Agent 已经具备 ReAct Tool-Use 基础，但还缺 3 个核心：

### 12.1 缺显式任务状态

现在很多 TODO 只存在于模型文本里，前端和后端无法可靠判断：

- 哪些步骤完成了？
- 哪些步骤失败了？
- 哪些步骤被阻塞？
- 哪个产物对应哪个步骤？

应升级为 TaskGraph。

### 12.2 缺 CompletionAuditor

空工具返回时，必须用审计模块判断：

- 是否全部完成。
- 是否还有剩余 TODO。
- 是否工具缺失。
- 是否模型/API 失败。
- 是否应该继续、失败、阻塞、询问用户。

### 12.3 前后端状态协议不够严格

前端不应自行猜 completed。

后端必须明确告诉前端：

- completed
- incomplete
- blocked
- failed
- awaiting_approval

### 12.4 推荐下一步实施

P0：实现结构化任务状态和 CompletionAuditor。

P1：把 `done` 事件增加 `status`、`completed_steps`、`remaining_steps`、`artifacts`。

P2：前端 Final Report 改为读取后端真实报告，而不是用本地 computed 拼接“本轮任务已经结束”。

P3：为复杂链式任务写自动化测试：

```text
生成图片 → 图生视频 → 生成旁白 → 合成
```

验收标准：

- 至少调用对应工具。
- 每个工具结果被分析。
- 产物路径被传递。
- 未完成时不得显示 completed。
- API 403 时明确显示模型调用失败，不伪装成任务完成。

---

## 13. 一句话总结

2026 年主流 Agent 的核心趋势是：

> 从“LLM 自己边想边调工具”的 ReAct，升级为“显式任务状态 + 工具执行闭环 + 完成度审计 + 环境验证”的工程化 Agent。

对 ttsapp 来说，最关键的不是再加更多工具，而是建立：

```text
任务树 + 产物记忆 + 完成审计 + 严格状态协议
```

这样 Agent 才能真正完成复杂创作任务，而不是停留在“写计划、等用户继续、误判完成”的阶段。
