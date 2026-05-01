# P6 断线恢复、事件回放与 Tracing 设计

> 所属阶段：P6/P7  
> 状态：最小实现已落地  
> 目标：让长任务可恢复、可回放、可复盘。

---

## 1. 背景

漫剧任务涉及图片、视频、TTS、合成，耗时长，WebSocket 容易断开。没有事件回放会导致用户刷新后丢失状态。

## 2. 目标

- [x] 事件回放 API（`GET /tasks/{task_uid}/events` 已有）。
- [x] 任务取消 API（`POST /tasks/{task_uid}/cancel`）。
- [x] Trace 时间线（`EventTracer` + `GET /tasks/{task_uid}/trace`）。
- [x] 工具调用详情（`trace_tool_call` / `trace_llm_call`）。
- [ ] 断线恢复（前端回放逻辑）。
- [ ] 任务重试/恢复 API。
- [ ] 成功率/失败率统计。

## 3. 非目标

- 不实现分布式任务队列。
- 不实现完整 LangSmith。

## 4. 目标文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/api/v1/comic_agent.py` | 修改 | 增加任务控制/查询 API |
| `task_runtime/store.py` | 修改 | 查询事件和 trace |
| `frontend/src/views/comic-agent/ComicAgentView.vue` | 修改 | 事件回放和时间线 |

## 5. API 设计

```text
GET  /api/v1/comic-agent/tasks/{task_uid}
GET  /api/v1/comic-agent/tasks/{task_uid}/events
GET  /api/v1/comic-agent/tasks/{task_uid}/artifacts
POST /api/v1/comic-agent/tasks/{task_uid}/cancel
POST /api/v1/comic-agent/tasks/{task_uid}/retry
POST /api/v1/comic-agent/tasks/{task_uid}/resume
```

## 6. 断线恢复流程

```text
前端 reconnect
  ↓
携带 task_uid / conversation_id
  ↓
后端查询 AgentEvent
  ↓
前端回放事件重建工作台
  ↓
如果任务仍 running，继续监听或显示当前状态
```

## 7. Trace 记录

- LLM 调用摘要。
- tool_call 参数。
- ToolResult。
- step 状态变化。
- Auditor 决策。
- Replanner 决策。
- token 用量。
- duration。

## 8. TODO

- [x] 新建 `event_tracer.py`（TraceRecord + EventTracer）。
- [x] 实现 cancel API。
- [x] 实现 trace API（`GET /tasks/{task_uid}/trace`）。
- [ ] 前端支持事件回放。
- [ ] 实现 retry / resume API。
- [ ] 前端新增事件时间线。
- [ ] 后端统计成功率/失败率。

## 9. 验收标准

- [x] 用户能取消任务（cancel API）。
- [x] 任务可按时间线复盘（trace API）。
- [x] EventTracer 记录 LLM/工具/步骤/审计/重规划事件。
- [ ] 页面刷新后能恢复任务状态（前端）。
- [ ] 失败步骤能重试（retry API）。
