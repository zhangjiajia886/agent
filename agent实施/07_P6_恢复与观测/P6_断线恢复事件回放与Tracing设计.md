# P6 断线恢复、事件回放与 Tracing 设计

> 所属阶段：P6/P7  
> 状态：待实施  
> 目标：让长任务可恢复、可回放、可复盘。

---

## 1. 背景

漫剧任务涉及图片、视频、TTS、合成，耗时长，WebSocket 容易断开。没有事件回放会导致用户刷新后丢失状态。

## 2. 目标

- [ ] 事件回放 API。
- [ ] 断线恢复。
- [ ] 任务取消/重试/恢复。
- [ ] Trace 时间线。
- [ ] 工具调用详情。
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

- [ ] 实现事件查询 API。
- [ ] 前端支持事件回放。
- [ ] 实现 cancel API。
- [ ] 实现 retry API。
- [ ] 实现 resume API。
- [ ] 前端新增事件时间线。
- [ ] 前端新增工具调用详情。
- [ ] 后端统计成功率/失败率。

## 9. 验收标准

- [ ] 页面刷新后能恢复任务状态。
- [ ] 断线后能重新查看步骤和产物。
- [ ] 用户能取消任务。
- [ ] 失败步骤能重试。
- [ ] 任务可按时间线复盘。
