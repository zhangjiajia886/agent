# P4 CompletionAuditor 设计

> 所属阶段：P4  
> 状态：最小实现已落地  
> 目标：任务完成状态由系统规则判定，不由模型文本决定。

---

## 1. 背景

当前 P0 有简化 `audit_task()`，但还不够完整。复杂任务必须根据 TaskGraph、Step、Artifact、ToolInvocation 统一审计。

## 2. 目标

- [x] 独立 `CompletionAuditor` 模块。
- [x] 规则判定 completed/incomplete/blocked/failed/canceled。
- [x] 支持 required step。
- [x] 支持 partial 成功（skipped 计入完成）。
- [x] `audit_task()` 委托给 `CompletionAuditor`。
- [ ] 支持 required artifact 校验。
- [ ] Reporter 独立模块。

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

- [x] 新建 `completion_auditor.py`。
- [x] 从 P0 `audit_task()` 迁移规则并增强。
- [x] 增加 5 级优先判定（canceled > failed > blocked > incomplete > completed）。
- [x] `next_action` 提示（replanner / ask_user）。
- [ ] 新建 `reporter.py`。
- [ ] 增加 artifact verified 判定。
- [ ] 前端优先展示后端 final_report。

## 9. 验收标准

- [x] required step 未完成时不会 completed。
- [x] failed step 时任务 failed + next_action=replanner。
- [x] blocked step 时任务 blocked + next_action=ask_user。
- [x] 所有 required step 完成时任务 completed。
- [ ] artifact verified 校验。
