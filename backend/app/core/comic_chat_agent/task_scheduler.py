"""
P3 TaskScheduler —— 基于 depends_on 的步骤调度器。

负责计算 ready steps、管理步骤状态机，不负责执行。
执行仍由 agent_runner ReAct 循环完成。

设计模式：DAG Scheduler（P10 选型）。
实现 SchedulerProtocol（P10 接口契约）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger

from .task_runtime import RuntimeStep, RuntimeTask


# ═══════════════════ 步骤状态机 ═══════════════════

# pending → ready → running → succeeded / failed / blocked / canceled
# pending → blocked  (上游 failed 时)
# pending → skipped  (非 required 且不满足条件)

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "blocked", "canceled", "skipped"})
SUCCESS_STATUSES = frozenset({"succeeded"})


# ═══════════════════ Scheduler 决策 ═══════════════════

@dataclass
class ScheduleDecision:
    ready_steps: list[RuntimeStep]
    blocked_steps: list[RuntimeStep]
    all_done: bool


# ═══════════════════ TaskScheduler ═══════════════════

class TaskScheduler:
    """
    DAG Scheduler：基于 depends_on 计算 ready steps。

    调用方式：
        scheduler = TaskScheduler(runtime_task)
        decision = scheduler.evaluate()
        for step in decision.ready_steps:
            # execute step ...
            scheduler.mark_succeeded(step)
    """

    def __init__(self, task: RuntimeTask):
        self.task = task
        self._step_map: dict[str, RuntimeStep] = {
            s.step_uid: s for s in task.steps
        }

    def _get_step(self, uid: str) -> RuntimeStep | None:
        return self._step_map.get(uid)

    # ── 状态查询 ──

    def is_step_done(self, step: RuntimeStep) -> bool:
        return step.status in TERMINAL_STATUSES

    def is_step_succeeded(self, step: RuntimeStep) -> bool:
        return step.status in SUCCESS_STATUSES

    def is_all_done(self) -> bool:
        return all(self.is_step_done(s) for s in self.task.steps)

    def has_any_failed(self) -> bool:
        return any(s.status == "failed" for s in self.task.steps)

    # ── 依赖检查 ──

    def _deps_satisfied(self, step: RuntimeStep) -> bool:
        """所有 depends_on 步骤均 succeeded。"""
        for dep_uid in step.depends_on:
            dep = self._get_step(dep_uid)
            if dep is None or not self.is_step_succeeded(dep):
                return False
        return True

    def _deps_blocked(self, step: RuntimeStep) -> bool:
        """任一 depends_on 步骤处于 failed/blocked/canceled。"""
        for dep_uid in step.depends_on:
            dep = self._get_step(dep_uid)
            if dep is not None and dep.status in ("failed", "blocked", "canceled"):
                return True
        return False

    # ── 核心计算 ──

    def get_ready_steps(self) -> list[RuntimeStep]:
        """返回当前可执行的步骤。"""
        ready = []
        for step in self.task.steps:
            if step.status != "pending":
                continue
            if self._deps_satisfied(step):
                ready.append(step)
        return ready

    def get_blocked_steps(self) -> list[RuntimeStep]:
        """返回因上游失败而被阻塞的步骤。"""
        blocked = []
        for step in self.task.steps:
            if step.status != "pending":
                continue
            if self._deps_blocked(step):
                blocked.append(step)
        return blocked

    def evaluate(self) -> ScheduleDecision:
        """综合评估当前调度状态。"""
        # 先标记因上游失败被阻塞的步骤
        blocked = self.get_blocked_steps()
        for step in blocked:
            self.mark_blocked(step, reason="上游步骤失败")

        ready = self.get_ready_steps()
        all_done = self.is_all_done()
        return ScheduleDecision(
            ready_steps=ready,
            blocked_steps=blocked,
            all_done=all_done,
        )

    # ── 状态变迁 ──

    def mark_ready(self, step: RuntimeStep) -> None:
        if step.status == "pending":
            step.status = "ready"
            logger.debug(f"[Scheduler] {step.step_uid} → ready")

    def mark_running(self, step: RuntimeStep) -> None:
        step.status = "running"
        self.task.current_step_uid = step.step_uid
        logger.debug(f"[Scheduler] {step.step_uid} → running")

    def mark_succeeded(self, step: RuntimeStep, outputs: dict[str, Any] | None = None) -> None:
        step.status = "succeeded"
        if outputs:
            step.outputs = outputs
        logger.debug(f"[Scheduler] {step.step_uid} → succeeded")

    def mark_failed(self, step: RuntimeStep, error: dict[str, Any] | None = None) -> None:
        step.status = "failed"
        if error:
            step.error = error
        logger.warning(f"[Scheduler] {step.step_uid} → failed")

    def mark_blocked(self, step: RuntimeStep, reason: str = "") -> None:
        step.status = "blocked"
        step.error = {"message": reason or "上游依赖未满足"}
        logger.info(f"[Scheduler] {step.step_uid} → blocked: {reason}")

    def mark_canceled(self, step: RuntimeStep, reason: str = "") -> None:
        step.status = "canceled"
        step.error = {"message": reason or "已取消"}

    # ── 上游产物收集 ──

    def collect_upstream_outputs(self, step: RuntimeStep) -> dict[str, Any]:
        """收集当前 step 的所有上游步骤的 outputs。"""
        collected: dict[str, Any] = {}
        for dep_uid in step.depends_on:
            dep = self._get_step(dep_uid)
            if dep and dep.outputs:
                for k, v in dep.outputs.items():
                    collected[k] = v
        return collected

    # ── 统计 ──

    def summary(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for s in self.task.steps:
            status_counts[s.status] = status_counts.get(s.status, 0) + 1
        return {
            "total_steps": len(self.task.steps),
            "status_counts": status_counts,
            "all_done": self.is_all_done(),
            "has_failed": self.has_any_failed(),
        }
