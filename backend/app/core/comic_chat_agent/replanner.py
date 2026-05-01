"""
P5 Replanner —— 工具失败后的系统级恢复策略。

不让 LLM 自行猜测重试/跳过，由 RecoveryPolicy 规则决策。
策略：retry → fallback_tool → ask_user → skip → block → fail。

设计模式：Recovery Policy（P10 选型）。
实现 ReplannerProtocol（P10 接口契约）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger

from .tool_capability import get_capability, get_fallbacks
from .task_runtime import RuntimeStep, RuntimeTask


# ═══════════════════ ReplanDecision ═══════════════════

ReplanAction = Literal["retry", "fallback_tool", "ask_user", "skip", "block", "fail"]


@dataclass
class ReplanDecision:
    action: ReplanAction = "fail"
    step_uid: str = ""
    reason: str = ""
    next_tool: str | None = None
    patched_inputs: dict[str, Any] | None = None
    question: str | None = None
    choices: list[str] | None = None


# ═══════════════════ RecoveryPolicy ═══════════════════

@dataclass
class RecoveryPolicy:
    """每个 step 的恢复策略配置。"""
    max_retries: int = 2
    max_fallback_attempts: int = 2
    allow_skip: bool = False    # 非 required step 可 skip
    allow_ask_user: bool = True


# ═══════════════════ 步骤重试计数 ═══════════════════

@dataclass
class StepRetryState:
    retry_count: int = 0
    fallback_index: int = 0
    fallback_attempts: int = 0
    user_rejected: bool = False


# ═══════════════════ Replanner ═══════════════════

class Replanner:
    """
    工具失败后的恢复决策引擎。

    决策流程：
    1. 检查 retry_count < max_retries → retry
    2. 检查 fallback_tools 可用 → fallback_tool
    3. 检查 allow_ask_user → ask_user
    4. 检查 allow_skip → skip
    5. → fail / block

    防循环：
    - 每个 step 独立的 StepRetryState
    - 总工具预算由 BudgetController 外部控制
    - 用户拒绝后不重复调用同一工具
    """

    def __init__(self, default_policy: RecoveryPolicy | None = None):
        self._default_policy = default_policy or RecoveryPolicy()
        self._states: dict[str, StepRetryState] = {}

    def _get_state(self, step_uid: str) -> StepRetryState:
        if step_uid not in self._states:
            self._states[step_uid] = StepRetryState()
        return self._states[step_uid]

    def _get_policy(self, step: RuntimeStep) -> RecoveryPolicy:
        return self._default_policy

    # ── 核心决策 ──

    def decide(
        self,
        task: RuntimeTask,
        failed_step: RuntimeStep,
        error: dict[str, Any] | None = None,
        *,
        enabled_tools: set[str] | None = None,
    ) -> ReplanDecision:
        """根据失败步骤和恢复策略生成 ReplanDecision。"""
        state = self._get_state(failed_step.step_uid)
        policy = self._get_policy(failed_step)
        tool_name = failed_step.tool_name or ""
        error_msg = (error or {}).get("message", "") if error else ""

        # ── 用户已拒绝 → 不再重试同工具 ──
        if state.user_rejected:
            return ReplanDecision(
                action="block",
                step_uid=failed_step.step_uid,
                reason=f"用户已拒绝工具 {tool_name}",
            )

        # ── 1. retry ──
        if state.retry_count < policy.max_retries and self._is_retryable(error):
            state.retry_count += 1
            logger.info(
                f"[Replanner] {failed_step.step_uid} retry {state.retry_count}/{policy.max_retries}"
            )
            return ReplanDecision(
                action="retry",
                step_uid=failed_step.step_uid,
                reason=f"重试 {state.retry_count}/{policy.max_retries}",
                next_tool=tool_name,
            )

        # ── 2. fallback_tool ──
        fallbacks = list(get_fallbacks(tool_name))
        if enabled_tools is not None:
            fallbacks = [f for f in fallbacks if f in enabled_tools]
        while state.fallback_index < len(fallbacks):
            fb = fallbacks[state.fallback_index]
            if state.fallback_attempts < policy.max_fallback_attempts:
                state.fallback_attempts += 1
                logger.info(
                    f"[Replanner] {failed_step.step_uid} fallback → {fb} "
                    f"(attempt {state.fallback_attempts})"
                )
                return ReplanDecision(
                    action="fallback_tool",
                    step_uid=failed_step.step_uid,
                    reason=f"切换到 fallback 工具 {fb}",
                    next_tool=fb,
                )
            # 当前 fallback 用尽，尝试下一个
            state.fallback_index += 1
            state.fallback_attempts = 0

        # ── 3. ask_user ──
        if policy.allow_ask_user:
            return ReplanDecision(
                action="ask_user",
                step_uid=failed_step.step_uid,
                reason=f"工具 {tool_name} 失败且无可用 fallback",
                question=f"步骤「{failed_step.title}」执行失败：{error_msg}。是否跳过或手动提供输入？",
                choices=["跳过此步骤", "重试", "终止任务"],
            )

        # ── 4. skip（非 required step）──
        if policy.allow_skip:
            return ReplanDecision(
                action="skip",
                step_uid=failed_step.step_uid,
                reason="非必须步骤，已跳过",
            )

        # ── 5. fail ──
        return ReplanDecision(
            action="fail",
            step_uid=failed_step.step_uid,
            reason=f"工具 {tool_name} 失败，已耗尽所有恢复策略",
        )

    # ── 用户回复处理 ──

    def handle_user_response(
        self,
        step_uid: str,
        response: str,
    ) -> ReplanAction:
        """处理 ask_user 后的用户回复，返回最终 action。"""
        state = self._get_state(step_uid)
        resp = response.strip()
        if resp in ("跳过此步骤", "skip"):
            return "skip"
        if resp in ("重试", "retry"):
            state.retry_count = 0
            state.fallback_index = 0
            state.fallback_attempts = 0
            return "retry"
        if resp in ("终止任务", "fail", "cancel"):
            return "fail"
        # 用户拒绝
        state.user_rejected = True
        return "block"

    # ── 辅助 ──

    @staticmethod
    def _is_retryable(error: dict[str, Any] | None) -> bool:
        """判断错误是否可重试（超时、网络等临时错误）。"""
        if not error:
            return False
        msg = str(error.get("message", "")).lower()
        retryable_patterns = (
            "timeout", "超时", "timed out",
            "connection", "连接", "network",
            "502", "503", "504",
            "temporarily", "临时",
            "rate limit", "限流",
        )
        return any(p in msg for p in retryable_patterns)

    def reset_step(self, step_uid: str) -> None:
        """重置某 step 的重试状态。"""
        if step_uid in self._states:
            del self._states[step_uid]
