# P5 Replanner 与 RecoveryPolicy 设计

> 所属阶段：P5  
> 状态：待实施  
> 目标：工具失败后按策略 retry/fallback/ask_user/block/fail，而不是让 LLM 自行猜测。

---

## 1. 背景

当前工具失败后主要依赖 LLM 阅读错误并继续，容易出现无限重试、误判完成或伪造产物路径。

P5 要引入系统级恢复策略。

## 2. 目标

- [ ] 独立 `Replanner`。
- [ ] 定义 RecoveryPolicy。
- [ ] 支持 retry。
- [ ] 支持 fallback_tool。
- [ ] 支持 ask_user。
- [ ] 支持 skip/block/fail。
- [ ] 防止无限循环。

## 3. 非目标

- 不让 LLM 任意重写整个任务图。
- 不自动执行高风险 fallback。

## 4. 目标文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `task_runtime/replanner.py` | 新增 | 重规划策略 |
| `task_runtime/scheduler.py` | 修改 | 接入 replan 决策 |
| `task_runtime/auditor.py` | 修改 | 使用 replan 后状态 |
| `frontend/src/views/comic-agent/ComicAgentView.vue` | 修改 | ask_user 展示 |

## 5. ReplanInput

```python
@dataclass
class ReplanInput:
    task: AgentTask
    failed_step: AgentStep
    tool_result: ToolResult
    available_tools: list[ToolRegistry]
    artifacts: list[AgentArtifact]
```

## 6. ReplanDecision

```python
@dataclass
class ReplanDecision:
    action: Literal['retry', 'fallback_tool', 'ask_user', 'skip', 'block', 'fail']
    step_uid: str
    reason: str
    next_tool: str | None
    patched_inputs: dict | None
    question: str | None
    choices: list[str] | None
```

## 7. 策略表

| 场景 | 策略 |
|---|---|
| ComfyUI 不可达 | fallback 到即梦或 blocked |
| ComfyUI 超时 | 降参数 retry 一次，再 fallback |
| 图生视频失败 | fallback 到即梦视频 |
| TTS 失败 | 换模型或 ask_user |
| 缺图片输入 | 查 ArtifactMemory；没有则 ask_user |
| 用户拒绝关键步骤 | canceled |
| 用户拒绝非关键步骤 | skipped 或 ask_user |

## 8. 防循环规则

- [ ] 每个 step 最大 retry 次数。
- [ ] 每个 fallback tool 最大调用次数。
- [ ] 总工具调用预算。
- [ ] 用户拒绝后不得重复调用同一工具。

## 9. TODO

- [ ] 新建 `replanner.py`。
- [ ] 实现 retry 策略。
- [ ] 实现 fallback_tool 策略。
- [ ] 实现 ask_user 事件。
- [ ] 前端支持 ask_user 选择。
- [ ] 实现循环预算控制。

## 10. 验收标准

- [ ] ComfyUI 图片失败可 fallback 到即梦图片。
- [ ] 图生视频失败可 fallback 到即梦视频。
- [ ] 缺输入时 ask_user，不伪造路径。
- [ ] 连续失败后任务进入 failed/blocked。
