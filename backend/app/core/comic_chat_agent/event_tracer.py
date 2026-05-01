"""
P6 EventTracer —— 任务事件追踪与时间线记录。

为长任务提供可复盘的 Trace 时间线：
- LLM 调用摘要
- 工具调用参数/结果/耗时
- Step 状态变迁
- Auditor / Replanner 决策
- Token 用量
- 预算消耗

设计模式：Observer（P10 选型）。
实现 EventReplayerProtocol（P10 接口契约）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════ Trace 类型 ═══════════════════

class TraceType(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    STEP_STATUS = "step_status"
    AUDIT = "audit"
    REPLAN = "replan"
    BUDGET = "budget"
    SANDBOX = "sandbox"
    APPROVAL = "approval"
    ERROR = "error"


# ═══════════════════ TraceRecord ═══════════════════

@dataclass
class TraceRecord:
    trace_type: TraceType
    timestamp: float = field(default_factory=time.time)
    task_uid: str = ""
    step_uid: str = ""
    tool_name: str = ""
    duration_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trace_type": self.trace_type.value,
            "timestamp": self.timestamp,
            "task_uid": self.task_uid,
            "duration_ms": self.duration_ms,
        }
        if self.step_uid:
            d["step_uid"] = self.step_uid
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.data:
            d["data"] = self.data
        return d


# ═══════════════════ EventTracer ═══════════════════

class EventTracer:
    """
    任务级事件追踪器。

    收集任务执行过程中的所有 trace 记录，用于：
    - 事件回放 API
    - 任务时间线复盘
    - 性能和成本分析
    """

    def __init__(self, task_uid: str = ""):
        self.task_uid = task_uid
        self._records: list[TraceRecord] = []
        self._start_time: float = time.time()

    # ── 记录 ──

    def record(self, trace_type: TraceType, **kwargs: Any) -> TraceRecord:
        r = TraceRecord(
            trace_type=trace_type,
            task_uid=self.task_uid,
            **kwargs,
        )
        self._records.append(r)
        return r

    def trace_llm_call(
        self,
        *,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: float = 0.0,
        iteration: int = 0,
    ) -> TraceRecord:
        return self.record(
            TraceType.LLM_CALL,
            duration_ms=duration_ms,
            data={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "iteration": iteration,
            },
        )

    def trace_tool_call(
        self,
        *,
        step_uid: str = "",
        tool_name: str = "",
        tool_input: dict[str, Any] | None = None,
        tool_output: dict[str, Any] | None = None,
        status: str = "",
        duration_ms: float = 0.0,
        error: str = "",
    ) -> TraceRecord:
        data: dict[str, Any] = {"status": status}
        if tool_input:
            data["input"] = tool_input
        if tool_output:
            data["output"] = _truncate_output(tool_output)
        if error:
            data["error"] = error
        return self.record(
            TraceType.TOOL_CALL,
            step_uid=step_uid,
            tool_name=tool_name,
            duration_ms=duration_ms,
            data=data,
        )

    def trace_step_status(
        self,
        *,
        step_uid: str = "",
        old_status: str = "",
        new_status: str = "",
    ) -> TraceRecord:
        return self.record(
            TraceType.STEP_STATUS,
            step_uid=step_uid,
            data={"old_status": old_status, "new_status": new_status},
        )

    def trace_audit(self, *, result: dict[str, Any]) -> TraceRecord:
        return self.record(TraceType.AUDIT, data=result)

    def trace_replan(self, *, decision: dict[str, Any]) -> TraceRecord:
        return self.record(TraceType.REPLAN, data=decision)

    def trace_budget(self, *, message: str, usage_pct: float = 0.0) -> TraceRecord:
        return self.record(
            TraceType.BUDGET,
            data={"message": message, "usage_pct": usage_pct},
        )

    # ── 查询 ──

    @property
    def records(self) -> list[TraceRecord]:
        return list(self._records)

    def get_by_type(self, trace_type: TraceType) -> list[TraceRecord]:
        return [r for r in self._records if r.trace_type == trace_type]

    def get_timeline(self) -> list[dict[str, Any]]:
        """返回完整时间线（按时间排序）。"""
        return [r.to_dict() for r in sorted(self._records, key=lambda r: r.timestamp)]

    def summary(self) -> dict[str, Any]:
        """返回追踪摘要。"""
        total_duration = time.time() - self._start_time
        type_counts: dict[str, int] = {}
        for r in self._records:
            type_counts[r.trace_type.value] = type_counts.get(r.trace_type.value, 0) + 1

        tool_calls = self.get_by_type(TraceType.TOOL_CALL)
        tool_durations: dict[str, float] = {}
        for tc in tool_calls:
            name = tc.tool_name or "unknown"
            tool_durations[name] = tool_durations.get(name, 0) + tc.duration_ms

        return {
            "task_uid": self.task_uid,
            "total_records": len(self._records),
            "total_duration_ms": round(total_duration * 1000, 1),
            "type_counts": type_counts,
            "tool_durations_ms": tool_durations,
        }


# ═══════════════════ 辅助 ═══════════════════

def _truncate_output(output: dict[str, Any], max_len: int = 500) -> dict[str, Any]:
    """截断过长的输出字段，避免 trace 体积膨胀。"""
    result = {}
    for k, v in output.items():
        if isinstance(v, str) and len(v) > max_len:
            result[k] = v[:max_len] + "...(truncated)"
        else:
            result[k] = v
    return result
