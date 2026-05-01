# P4 CompletionAuditor 设计

> 所属阶段：P4  
> 状态：待实施  
> 目标：任务完成状态由系统规则判定，不由模型文本决定。

---

## 1. 背景

当前 P0 有简化 `audit_task()`，但还不够完整。复杂任务必须根据 TaskGraph、Step、Artifact、ToolInvocation 统一审计。

## 2. 目标

- [ ] 独立 `CompletionAuditor` 模块。
- [ ] 规则判定 completed/incomplete/blocked/failed/canceled。
- [ ] 支持 required step。
- [ ] 支持 required artifact。
- [ ] 支持 partial 成功。
- [ ] Reporter 只负责解释，不负责判定。

## 3. 非目标

- 不让 LLM 作为唯一完成判断。
- 不做主观图片质量审美判断。

## 4. 目标文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `task_runtime/auditor.py` | 新增 | 审计规则 |
| `task_runtime/reporter.py` | 新增 | final_report 生成 |
| `task_runtime/store.py` | 修改 | 提供审计输入 |
| `agent_runner.py` | 修改 | 调用 auditor/reporter |

## 5. AuditInput

```python
@dataclass
class AuditInput:
    task: AgentTask
    steps: list[AgentStep]
    artifacts: list[AgentArtifact]
    tool_invocations: list[ToolInvocation]
    last_llm_text: str | None
```

## 6. AuditResult

```python
@dataclass
class AuditResult:
    status: str
    complete: bool
    reason: str
    completed_steps: list[str]
    remaining_steps: list[str]
    failed_steps: list[str]
    blocked_steps: list[str]
    next_action: dict | None
```

## 7. 判定优先级

```text
canceled
  > failed 不可恢复
  > blocked 需用户输入
  > incomplete 有 required 未完成
  > completed 所有 required 完成且 artifact verified
```

## 8. TODO

- [ ] 新建 `auditor.py`。
- [ ] 新建 `reporter.py`。
- [ ] 从 P0 `audit_task()` 迁移规则。
- [ ] 增加 required step 判定。
- [ ] 增加 artifact verified 判定。
- [ ] 增加 final_report 构造。
- [ ] 前端优先展示后端 final_report。

## 9. 验收标准

- [ ] required step 未完成时不会 completed。
- [ ] failed step 不可恢复时任务 failed。
- [ ] blocked step 需要用户输入时任务 blocked。
- [ ] 所有 required step 和 artifact 完成时任务 completed。
