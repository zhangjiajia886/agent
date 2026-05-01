# P3 Scheduler 与 StepExecutor 设计

> 所属阶段：P3  
> 状态：最小实现已落地  
> 目标：让系统调度 TaskGraph，LLM 只执行当前 step。

---

## 1. 背景

旧 ReAct 模式中，LLM 自己决定整个任务下一步，容易出现只列计划、不执行、跳步、误判完成。

P3 要把控制权转移给系统：

```text
Scheduler 决定执行哪个 step
StepExecutor 只执行当前 step
```

## 2. 目标

- [x] 实现 ready step 计算（`get_ready_steps`）。
- [x] 实现依赖顺序控制（`_deps_satisfied` / `_deps_blocked`）。
- [x] 实现步骤状态机（pending → ready → running → succeeded/failed/blocked）。
- [x] 上游产物收集（`collect_upstream_outputs`）。
- [x] 保持旧 `agent_runner.py` 兼容入口。
- [x] step 级执行上下文构建（StepExecutor）。
- [ ] agent_runner 主循环改造为 Scheduler 驱动。

## 3. 非目标

- 不做复杂分布式调度。
- 不做真正多 worker。
- 不做跨服务任务队列。

## 4. 目标文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `task_runtime/scheduler.py` | 新增 | 计算 ready steps |
| `task_runtime/step_executor.py` | 新增 | step 级 ReAct 执行 |
| `task_runtime/store.py` | 修改 | 查询/更新 step 状态 |
| `agent_runner.py` | 修改 | 调用 Scheduler/StepExecutor |

## 5. Scheduler 规则

```text
pending step
  ↓
所有 depends_on step 均 succeeded
  ↓
ready
  ↓
审批策略允许
  ↓
running
  ↓
succeeded / failed / blocked / canceled
```

## 6. StepExecutor 输入

```text
当前 step
用户原始目标
上游 artifacts
可用工具 schema
对话摘要
模型配置
```

## 7. StepExecutor Prompt 约束

```text
你正在执行 TaskGraph 中的单个步骤。
只能完成当前 step。
不得跳到其他 step。
如果当前 step 需要工具，必须返回 tool_call。
如果缺少输入，返回 structured_blocked。
```

## 8. 数据流

```text
TaskScheduler.get_ready_steps
  ↓
StepExecutor.execute(step)
  ↓
ToolExecutor.execute_tool
  ↓
ToolResultNormalizer
  ↓
Observer
  ↓
Store.update_step
  ↓
Auditor
```

## 9. TODO

- [x] 新建 `task_scheduler.py`。
- [x] 实现 `get_ready_steps()` / `get_blocked_steps()` / `evaluate()`。
- [x] 实现 `mark_running` / `mark_succeeded` / `mark_failed` / `mark_blocked`。
- [x] RuntimeStep 增加 `depends_on` 字段。
- [x] TaskPlanner 写入 `depends_on` 到 RuntimeStep。
- [x] 新建 `step_executor.py`（StepContext + StepExecutor）。
- [x] 主循环已接入 Scheduler / Replanner / EventTracer。
- [ ] 改造主循环为完全 Scheduler 驱动。
- [x] 保留旧 ReAct fallback。

## 10. 验收标准

- [x] `get_ready_steps` 只返回依赖全部 succeeded 的 pending step。
- [x] 上游 failed 时下游自动 blocked。
- [x] 每个 step 状态可追踪（status + summary）。
- [ ] 图片未生成前不会执行图生视频（待主循环改造）。
- [ ] LLM 输出跨步骤计划不会改变 Scheduler 决策（待主循环改造）。
