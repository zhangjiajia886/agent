"""
Agent 核心模块 Protocol 定义 —— P10 设计模式选型产出。

为 P2-P6 模块建立统一接口契约，后续各模块只需实现对应 Protocol。
当前阶段不强制使用 ABC 注册，仅用 typing.Protocol 做结构化子类型约束。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .task_runtime import RuntimeStep, RuntimeTask
from .tool_result import ToolResult


# ═══════════════════ P2 TaskPlanner ═══════════════════

@runtime_checkable
class TaskPlannerProtocol(Protocol):
    """
    Plan-and-Execute 模式：接收用户目标，返回初始 TaskGraph。
    当前 P0 实现 = task_runtime.create_runtime_task + infer_task_steps。
    P2 升级后应支持工具能力元数据驱动的规划。
    """

    async def plan(
        self,
        user_goal: str,
        *,
        available_tools: list[dict[str, Any]] | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> RuntimeTask: ...


# ═══════════════════ P3 Scheduler ═══════════════════

@runtime_checkable
class StepSchedulerProtocol(Protocol):
    """
    DAG 调度器：从 TaskGraph 中选出 ready steps。
    ready = 所有 depends_on 的 step 均已 succeeded。
    """

    def get_ready_steps(self, task: RuntimeTask) -> list[RuntimeStep]: ...

    def mark_step_running(self, task: RuntimeTask, step: RuntimeStep) -> None: ...


# ═══════════════════ P3 StepExecutor ═══════════════════

@runtime_checkable
class StepExecutorProtocol(Protocol):
    """
    单步执行器：接收 step 和工具参数，返回 ToolResult。
    当前 P0 实现 = tool_executor.execute_tool + normalize_tool_result。
    P3 升级后应支持 sandbox / budget 拦截。
    """

    async def execute(
        self,
        step: RuntimeStep,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult: ...


# ═══════════════════ P4 CompletionAuditor ═══════════════════

@dataclass
class AuditResult:
    """审计结果。"""
    complete: bool = False
    status: str = "incomplete"
    reason: str = ""
    remaining_steps: list[dict[str, Any]] = field(default_factory=list)
    failed_steps: list[dict[str, Any]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@runtime_checkable
class CompletionAuditorProtocol(Protocol):
    """
    完成度审计器：基于规则（非 LLM 自述）判断任务是否真正完成。
    当前 P0 实现 = task_runtime.audit_task。
    P4 升级后应支持产物校验、文件存在性检查等。
    """

    def audit(self, task: RuntimeTask, last_text: str = "") -> AuditResult: ...


# ═══════════════════ P5 Replanner ═══════════════════

@dataclass
class RecoveryDecision:
    """恢复策略决策。"""
    action: str = "fail"  # retry | fallback | ask_user | block | fail | skip
    fallback_tool: str | None = None
    retry_count: int = 0
    reason: str = ""


@runtime_checkable
class ReplannerProtocol(Protocol):
    """
    失败恢复策略：step 失败后决定 retry / fallback / ask_user / block / fail。
    当前 P0 没有 replanner，失败直接标记 step.status=failed。
    """

    def decide(
        self,
        task: RuntimeTask,
        step: RuntimeStep,
        error: dict[str, Any] | None,
    ) -> RecoveryDecision: ...

    async def replan(
        self,
        task: RuntimeTask,
        decision: RecoveryDecision,
    ) -> RuntimeTask: ...


# ═══════════════════ P6 EventReplayer ═══════════════════

@runtime_checkable
class EventReplayerProtocol(Protocol):
    """
    事件回放器：断线恢复时，从 DB 读取 AgentEvent 重建前端状态。
    """

    async def replay(
        self,
        task_uid: str,
        *,
        after_event_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]: ...
