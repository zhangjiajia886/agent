# P3 Scheduler 与 StepExecutor 设计

> 所属阶段：P3  
> 状态：待实施  
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

- [ ] 实现 ready step 计算。
- [ ] 实现 step 级 ReAct 执行。
- [ ] 实现依赖顺序控制。
- [ ] 初步支持可并行步骤的顺序执行。
- [ ] 保持旧 `agent_runner.py` 兼容入口。

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

- [ ] 新建 `scheduler.py`。
- [ ] 新建 `step_executor.py`。
- [ ] 实现 `get_ready_steps()`。
- [ ] 实现 `mark_ready_steps()`。
- [ ] 实现 `execute_step()`。
- [ ] 改造 `agent_runner.py` 主循环。
- [ ] 保留旧 ReAct fallback。

## 10. 验收标准

- [ ] 图片未生成前不会执行图生视频。
- [ ] TTS 和图生视频依赖满足后可执行。
- [ ] LLM 输出跨步骤计划不会改变 Scheduler 决策。
- [ ] 每个 step 状态可追踪。
