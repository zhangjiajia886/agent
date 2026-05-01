# P9 数据库与 Redis 状态层设计

> 所属阶段：P9  
> 状态：最小 Redis 状态层已落地  
> 目标：系统设计 Agent 的数据库权威状态与 Redis 运行时状态边界，为持久化、恢复、审批、限流、预算、调度打基础。

---

## 1. 背景

当前已有 `AgentTask / AgentStep / AgentArtifact / AgentEvent / ToolInvocation` 模型，但数据库设计还缺少索引、状态流转、事件增长策略、迁移策略。Redis 运行时状态尚未设计。

随着 Agent 支持长任务、自动执行、审批、预算、断线恢复，必须明确 DB 与 Redis 的职责边界。

## 2. 目标

- [x] 明确数据库权威状态边界。
- [x] 明确 Redis 临时运行状态边界。
- [ ] 设计 AgentTask 相关 ER 关系。
- [x] 设计 Redis key 和 TTL。
- [x] 设计 DB/Redis 一致性原则。
- [x] 设计任务锁、审批等待、预算计数、工具健康缓存。
- [x] 设计 AgentEvent 增长和分页策略。
- [ ] 设计迁移和清理策略。

## 3. 非目标

- 不在本阶段实现完整消息队列。
- 不把 Redis 作为长期权威状态。
- 不做复杂分布式事务。

## 4. 数据库职责

数据库保存长期、可恢复、可审计状态：

```text
AgentTask         任务主表
AgentStep         步骤表
AgentArtifact     产物表
AgentEvent        事件表
ToolInvocation    工具调用表
ToolRegistry      工具注册和能力元数据
ModelConfig       模型配置
AgentConversation 会话历史
AgentMessage      消息历史
```

## 5. ER 关系

```text
AgentConversation 1 ── N AgentTask
AgentTask         1 ── N AgentStep
AgentTask         1 ── N AgentArtifact
AgentTask         1 ── N AgentEvent
AgentTask         1 ── N ToolInvocation
AgentStep         1 ── N AgentArtifact
AgentStep         1 ── N ToolInvocation
```

## 6. 核心表策略

### 6.1 AgentTask

用途：任务权威状态。

关键索引：

```text
task_uid unique
conversation_id index
user_id index
status index
created_at index
```

### 6.2 AgentStep

用途：步骤状态、依赖、输入输出。

关键索引：

```text
step_uid unique
task_uid index
status index
tool_name index
sort_order
```

### 6.3 AgentEvent

用途：事件回放和审计。

关键索引：

```text
event_uid unique
task_uid index
step_uid index
event_type index
created_at index
```

事件增长策略：

- `delta` 不落库或降采样。
- `thinking` 限长保存。
- 结构化事件必须保存。
- 查询必须分页。
- 长期可按时间归档。

### 6.4 ToolInvocation

用途：工具调用审计。

必须记录：

- tool_call_id
- tool_name
- input
- output
- status
- error
- started_at
- finished_at
- duration

## 7. Redis 职责

Redis 保存运行中、高频、可过期状态：

```text
任务锁
审批等待
WebSocket 在线状态
预算临时计数
工具健康缓存
用户限流
取消/暂停/恢复信号
轻量任务队列
```

## 8. Redis Key 设计

```text
agent:task:{task_uid}:lock
agent:task:{task_uid}:approval
agent:task:{task_uid}:runtime
agent:task:{task_uid}:budget
agent:task:{task_uid}:cancel
agent:ws:user:{user_id}
agent:ws:conversation:{conversation_id}
agent:tool:{tool_name}:health
agent:rate:user:{user_id}:minute
agent:rate:user:{user_id}:day
agent:queue:tool:{tool_name}
```

## 9. Redis TTL 设计

| Key | TTL | 说明 |
|---|---:|---|
| `agent:task:{task_uid}:lock` | 10-30 分钟，心跳续期 | 防重复执行 |
| `agent:task:{task_uid}:approval` | 5-10 分钟 | 审批等待 |
| `agent:task:{task_uid}:runtime` | 1-24 小时 | 运行快照 |
| `agent:task:{task_uid}:budget` | 任务结束后 24 小时 | 高频预算计数 |
| `agent:task:{task_uid}:cancel` | 1 小时 | 取消信号 |
| `agent:ws:user:{user_id}` | 1-5 分钟 | 在线连接心跳 |
| `agent:tool:{tool_name}:health` | 30-120 秒 | 工具健康缓存 |
| `agent:rate:user:{user_id}:minute` | 60 秒 | 分钟限流 |
| `agent:rate:user:{user_id}:day` | 24 小时 | 日限流 |

当前最小实现位于 `backend/app/core/comic_chat_agent/agent_state.py`：

- `agent:task:{task_uid}:lock`：默认 60 分钟。
- `agent:task:{task_uid}:approval`：默认 5 分钟。
- `agent:task:{task_uid}:budget`：默认 24 小时。
- `agent:tool:{tool_name}:health`：默认 60 秒。

## 10. 一致性原则

```text
DB 是权威状态。
Redis 是临时协调状态。
Redis 可以丢，DB 不能丢。
```

具体规则：

- 任务最终状态以 `AgentTask.status` 为准。
- 当前是否运行可看 Redis lock，但恢复时必须回查 DB。
- 审批等待状态写 Redis，同时 `AgentEvent` 落库。
- 预算临时计数可在 Redis，最终 usage 写 DB。
- 工具健康可缓存 Redis，但工具调用结果写 DB。

## 11. 典型流程

### 11.1 启动任务

```text
create AgentTask in DB
  ↓
create AgentStep in DB
  ↓
set Redis task lock
  ↓
append task_created AgentEvent
```

### 11.2 审批等待

```text
step awaiting_approval 写 DB
  ↓
approval_required event 写 DB
  ↓
Redis 写 approval key，TTL 5 分钟
  ↓
用户响应后删除 approval key
```

### 11.3 断线恢复

```text
前端 reconnect
  ↓
查 DB AgentTask
  ↓
查 DB AgentEvent 分页回放
  ↓
检查 Redis lock 判断是否仍运行
  ↓
恢复前端工作台
```

## 12. 迁移策略

- 开发期可继续 `Base.metadata.create_all`。
- 生产前必须补 Alembic migration。
- 新字段优先 nullable 或 default，避免破坏旧数据。
- 大 JSON 字段保持可选，避免写入失败影响主流程。

## 13. 清理与归档

建议：

- AgentEvent 保留近期完整数据，长期归档。
- 失败任务保留完整事件。
- 成功任务可压缩 thinking 类事件。
- Artifact 文件定期校验是否存在。

## 14. TODO

- [x] 确认 Redis 是否已在项目依赖中。
- [x] 增加 Redis 配置项。
- [x] 新建 Redis client 模块。
- [x] 设计 task lock API。
- [x] 设计 approval key API。
- [x] 设计 budget counter API。
- [x] 为 AgentEvent 增加分页查询 API。
- [ ] 补 Alembic migration 计划。

## 15. 验收标准

- [x] DB 能查询任务完整状态。
- [x] Redis lock 能防止同一 task 重复执行。
- [x] Redis approval key 过期后任务能处理超时。
- [ ] Redis 工具健康缓存能被读取。
- [x] Redis 丢失不影响历史任务查询。
- [x] AgentEvent 支持按 task_uid 分页回放。
