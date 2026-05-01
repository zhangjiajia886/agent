"""
P4 CompletionAuditor —— 任务完成状态规则审计。

规则决定状态，LLM 解释状态。
替代 P0 task_runtime.audit_task 的简化逻辑。

判定优先级：canceled > failed > blocked > incomplete > completed。

设计模式：CompletionAuditor（P10 选型）。
实现 CompletionAuditorProtocol（P10 接口契约）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .task_runtime import RuntimeStep, RuntimeTask


# ═══════════════════ AuditResult ═══════════════════

@dataclass
class AuditResult:
    status: str = "incomplete"  # completed / incomplete / failed / blocked / canceled
    complete: bool = False
    reason: str = ""
    completed_steps: list[str] = field(default_factory=list)
    remaining_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    blocked_steps: list[str] = field(default_factory=list)
    canceled_steps: list[str] = field(default_factory=list)
    skipped_steps: list[str] = field(default_factory=list)
    next_action: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "complete": self.complete,
            "reason": self.reason,
            "completed_steps": self.completed_steps,
            "remaining_steps": self.remaining_steps,
            "failed_steps": self.failed_steps,
            "blocked_steps": self.blocked_steps,
        }
        if self.canceled_steps:
            d["canceled_steps"] = self.canceled_steps
        if self.skipped_steps:
            d["skipped_steps"] = self.skipped_steps
        if self.next_action:
            d["next_action"] = self.next_action
        return d


# ═══════════════════ CompletionAuditor ═══════════════════

class CompletionAuditor:
    """
    规则驱动的任务完成审计器。

    按优先级判定任务状态：
    1. canceled — 任务被用户取消
    2. failed — 存在不可恢复的 required step 失败
    3. blocked — 存在 required step 阻塞，需用户输入
    4. incomplete — 仍有 required step 未完成
    5. completed — 所有 required step 成功

    调用方式：
        auditor = CompletionAuditor()
        result = auditor.audit(runtime_task, last_text="...")
    """

    def audit(self, task: RuntimeTask, last_text: str = "") -> AuditResult:
        steps = task.steps
        if not steps:
            return AuditResult(
                status="completed",
                complete=True,
                reason="无规划步骤，视为完成。",
            )

        # ── 分类 ──
        succeeded: list[RuntimeStep] = []
        failed: list[RuntimeStep] = []
        blocked: list[RuntimeStep] = []
        canceled: list[RuntimeStep] = []
        skipped: list[RuntimeStep] = []
        remaining: list[RuntimeStep] = []

        for s in steps:
            if s.status == "succeeded":
                succeeded.append(s)
            elif s.status == "failed":
                failed.append(s)
            elif s.status == "blocked":
                blocked.append(s)
            elif s.status == "canceled":
                canceled.append(s)
            elif s.status == "skipped":
                skipped.append(s)
            else:
                remaining.append(s)

        # ── LLM 文本暗示未完成 ──
        text_incomplete = bool(
            last_text
            and re.search(
                r"剩余\s*TODO|尚未完成|未完成|还需要|需要继续|下一步",
                last_text,
            )
        )

        # ── 构造结果 ──
        result = AuditResult(
            completed_steps=[s.step_uid for s in succeeded],
            remaining_steps=[s.step_uid for s in remaining],
            failed_steps=[s.step_uid for s in failed],
            blocked_steps=[s.step_uid for s in blocked],
            canceled_steps=[s.step_uid for s in canceled],
            skipped_steps=[s.step_uid for s in skipped],
        )

        # ── 判定优先级 ──
        # 1. canceled
        if task.status == "canceled" or (canceled and not succeeded and not remaining):
            result.status = "canceled"
            result.reason = "任务已取消。"
            return result

        # 2. failed（required step 失败且无法恢复）
        if failed:
            result.status = "failed"
            result.reason = f"{len(failed)} 个步骤失败。"
            result.next_action = {"type": "replanner", "hint": "检查失败步骤，尝试 fallback 或重试"}
            return result

        # 3. blocked
        if blocked:
            result.status = "blocked"
            result.reason = f"{len(blocked)} 个步骤被阻塞，需要用户输入或上游修复。"
            result.next_action = {"type": "ask_user", "hint": "部分步骤被阻塞，请检查输入"}
            return result

        # 4. incomplete
        if remaining or text_incomplete:
            result.status = "incomplete"
            result.reason = f"仍有 {len(remaining)} 个步骤未完成。"
            return result

        # 5. completed
        result.status = "completed"
        result.complete = True
        total = len(steps)
        done = len(succeeded) + len(skipped)
        result.reason = f"所有规划步骤已完成（{done}/{total}）。"
        return result

    def audit_to_dict(self, task: RuntimeTask, last_text: str = "") -> dict[str, Any]:
        """兼容旧 audit_task 的 dict 返回格式。"""
        result = self.audit(task, last_text)
        d = result.to_dict()
        d["artifacts"] = task.artifacts
        return d
