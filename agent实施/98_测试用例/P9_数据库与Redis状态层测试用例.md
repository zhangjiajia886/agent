# P9 数据库与 Redis 状态层测试用例

## 用例 1：数据库权威状态

- **操作**：执行一次 Agent 工具任务
- **期望**：
  - [ ] `AgentTask` 有记录
  - [ ] `AgentStep` 有记录
  - [ ] `AgentEvent` 有关键事件
  - [ ] `ToolInvocation` 有工具调用记录
  - [ ] `AgentArtifact` 有产物记录

## 用例 2：事件分页回放

- **操作**：查询指定 `task_uid` 的事件
- **期望**：
  - [ ] 支持按 `created_at/id` 排序
  - [ ] 支持分页
  - [ ] 不返回过大的 delta 流

## 用例 3：Redis task lock

- **操作**：同一 `task_uid` 重复启动
- **期望**：
  - [ ] 第一次获取 lock 成功
  - [ ] 第二次被拒绝或等待
  - [ ] lock TTL 可续期
  - [ ] 任务结束后 lock 删除
- **最小实现对应方法**：
  - `AgentStateStore.acquire_task_lock`
  - `AgentStateStore.renew_task_lock`
  - `AgentStateStore.release_task_lock`

## 用例 4：Redis approval 状态

- **操作**：触发需审批工具
- **期望**：
  - [ ] 写入 `agent:task:{task_uid}:approval`
  - [ ] 用户确认后删除 key
  - [ ] 超时后 key 过期并触发 reject/timeout
- **最小实现对应方法**：
  - `AgentStateStore.set_approval_waiting`
  - `AgentStateStore.clear_approval`

## 用例 5：Redis budget counter

- **操作**：连续调用工具
- **期望**：
  - [ ] Redis 计数递增
  - [ ] 达到预算上限后阻止或 ask_user
  - [ ] 任务结束后 usage 写入 DB
- **最小实现对应方法**：
  - `AgentStateStore.increment_budget_counter`
  - `AgentStateStore.clear_budget_counter`

## 用例 6：Redis 丢失恢复

- **操作**：清空 Redis 后查询历史任务
- **期望**：
  - [ ] DB 中历史任务仍可查询
  - [ ] 已完成任务 final_report 不丢失
  - [ ] 已完成 artifact 不丢失

## 用例 7：工具健康缓存

- **操作**：检查 ComfyUI/Jimeng 健康状态
- **期望**：
  - [ ] 首次检查写入 Redis health key
  - [ ] TTL 内复用缓存
  - [ ] TTL 后重新检查
- **最小实现对应方法**：
  - `AgentStateStore.set_tool_health`
  - `AgentStateStore.get_tool_health`
