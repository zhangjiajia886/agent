# 漫剧 Agent 优化 TODO

> 来源：`漫剧agent深度优化设计.md`  
> 当前目标：先实现一个 P0 可运行版本，用后端权威任务状态替代纯前端推断，并为后续 TaskGraph / Auditor / Replanner 完整化打底。

---

## P0 当前状态

### 已完成

- [x] 新增后端任务状态模型：`backend/app/models/agent_task.py`
  - [x] `AgentTask`
  - [x] `AgentStep`
  - [x] `AgentArtifact`
  - [x] `AgentEvent`
  - [x] `ToolInvocation`
- [x] 注册新模型到 `backend/app/models/__init__.py`
- [x] 在 `backend/app/main.py` 导入 `app.models`，确保 `Base.metadata.create_all` 能发现新增表
- [x] 新增统一工具结果标准化：`backend/app/core/comic_chat_agent/tool_result.py`
  - [x] `ToolResult`
  - [x] `ArtifactPayload`
  - [x] `normalize_tool_result()`
- [x] 新增 P0 内存态任务运行时：`backend/app/core/comic_chat_agent/task_runtime.py`
  - [x] `RuntimeTask`
  - [x] `RuntimeStep`
  - [x] `create_runtime_task()`
  - [x] `task_created_event()`
  - [x] `task_update_event()`
  - [x] `step_update_event()`
  - [x] `artifact_created_event()`
  - [x] `audit_task()`
  - [x] `final_report_event()`
- [x] `agent_runner.py` 接入 P0 Runtime
  - [x] 任务开始时发送 `task_created`
  - [x] 工具审批前发送 `task_update` / `step_update`
  - [x] 工具执行前发送 `task_update` / `step_update` / `tool_start`
  - [x] 工具执行后发送 `tool_done.standard_result`
  - [x] 工具结果转为 `artifact_created` / `step_update`
  - [x] 结束时发送包含 `final_report` 的 `done`
- [x] 前端 Agent 事件类型扩展：`frontend/src/api/comic-agent.ts`
  - [x] `task_created`
  - [x] `task_update`
  - [x] `step_update`
  - [x] `artifact_created`
  - [x] `incomplete`
  - [x] `standard_result`
  - [x] `final_report`
- [x] 前端工作台接入后端状态事件：`ComicAgentView.vue`
  - [x] 任务图创建更新
  - [x] 步骤状态更新
  - [x] 产物登记
  - [x] 后端最终报告

### 待验证

- [ ] 后端 Python 语法检查通过
- [ ] 前端 TypeScript 构建通过
- [ ] 后端启动后自动创建新表
- [ ] WebSocket 普通问答不受影响
- [ ] WebSocket 工具任务能收到 `task_created` / `step_update` / `artifact_created` / `done.final_report`
- [ ] 自动执行模式下 ComfyUI / 即梦图片生成能正常生成产物并登记到工作台
- [ ] 工具失败时 step 状态为 `failed`，最终报告不是误判完成

---

## P0 边界

本版本不是完整 DAG 引擎，只实现“最小权威状态闭环”：

```text
用户目标
  ↓
内存态 RuntimeTask / RuntimeStep
  ↓
ReAct 工具执行
  ↓
标准 ToolResult
  ↓
Artifact 事件
  ↓
CompletionAuditor P0 审计
  ↓
FinalReport
```

P0 暂不实现：

- [ ] DB 持久化写入 `agent_task / agent_step / agent_artifact / agent_event / tool_invocation`
- [ ] 真正 DAG Scheduler
- [ ] Replanner 自动重规划
- [ ] 断线恢复和事件回放
- [ ] 复杂并行依赖调度

---

## P1 待办

- [ ] 将 RuntimeTask 状态持久化到数据库
- [ ] 将每次 WebSocket 事件写入 `AgentEvent`
- [ ] 将每次工具调用写入 `ToolInvocation`
- [ ] 实现 `TaskScheduler`
- [ ] 实现 `depends_on` 调度规则
- [ ] 实现 `CompletionAuditor` 独立模块
- [ ] 实现 `Replanner`
  - [ ] retry
  - [ ] fallback
  - [ ] ask_user
  - [ ] blocked
- [ ] 前端展示后端 `final_report` 详情
- [ ] 增加任务历史查询 API

---

## P2 待办

- [ ] 断线恢复
- [ ] 事件回放
- [ ] 任务取消
- [ ] 任务重试
- [ ] LangGraph-like 状态机抽象评估
- [ ] LangSmith-like tracing 面板
- [ ] 多 Agent 角色扩展：Director / Visual / Motion / Audio / Auditor

---

## 验收标准

P0 通过标准：

- [ ] 一次“生成图片”任务，前端显示后端 `task_created` 步骤
- [ ] 工具开始时对应 step 进入 `running`
- [ ] 工具成功后 step 进入 `completed`
- [ ] 图片产物进入 Artifact Gallery
- [ ] `done` 事件携带 `final_report`
- [ ] 如果模型只列计划不调用工具，前端显示 `incomplete` 或 `failed`，不再误判成功
- [ ] 旧版 `tool_start/tool_done/delta/done` 消费逻辑仍兼容
