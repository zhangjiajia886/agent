"""
P11 成本与预算控制。

统一管理 Agent 任务中 token、工具调用、视频/图片/音频生成次数和执行时间的预算。
替代 agent_runner 中散落的 MAX_TOOL_CALLS_PER_TOOL / TOKEN_BUDGET 等硬编码限制。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger

from .tool_capability import get_capability


# ═══════════════════ 预算决策 ═══════════════════

class BudgetAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    ASK_USER = "ask_user"
    BLOCK = "block"


@dataclass
class BudgetDecision:
    action: BudgetAction = BudgetAction.ALLOW
    category: str = ""       # token / tool / iteration / cost / duration
    message: str = ""
    usage_pct: float = 0.0   # 0.0 ~ 1.0+


# ═══════════════════ TaskBudget ═══════════════════

@dataclass
class TaskBudget:
    max_iterations: int = 15
    max_tool_calls: int = 40
    max_calls_per_tool: dict[str, int] = field(default_factory=lambda: {
        "generate_image": 8,
        "generate_image_with_face": 6,
        "edit_image": 4,
        "image_to_video": 3,
        "text_to_video": 3,
        "upscale_image": 4,
        "text_to_speech": 6,
        "merge_media": 2,
        "add_subtitle": 2,
        "read_file": 6,
        "write_file": 5,
        "edit_file": 4,
        "bash": 8,
        "python_exec": 5,
        "web_search": 4,
        "web_fetch": 4,
        "grep_search": 4,
        "find_files": 4,
        "list_dir": 4,
        "http_request": 4,
    })
    max_input_tokens: int = 32000
    max_output_tokens: int = 16000
    max_image_generations: int = 10
    max_video_generations: int = 3
    max_audio_generations: int = 6
    max_duration_seconds: int = 600
    warn_threshold: float = 0.75  # 达到 75% 时发出 warning


# ═══════════════════ BudgetUsage ═══════════════════

IMAGE_TOOLS = frozenset({
    "generate_image", "generate_image_with_face", "edit_image", "upscale_image",
    "jimeng_generate_image", "jimeng_reference_image", "jimeng_edit_image", "jimeng_upscale_image",
})
VIDEO_TOOLS = frozenset({
    "image_to_video", "text_to_video",
    "jimeng_generate_video", "jimeng_motion_mimic",
})
AUDIO_TOOLS = frozenset({
    "text_to_speech",
})


@dataclass
class BudgetUsage:
    iterations: int = 0
    tool_calls: int = 0
    calls_per_tool: dict[str, int] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    image_generations: int = 0
    video_generations: int = 0
    audio_generations: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def duration_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def estimated_cost(self) -> float:
        cost = 0.0
        cost += self.image_generations * 0.5
        cost += self.video_generations * 2.0
        cost += self.audio_generations * 0.1
        cost += (self.input_tokens / 1000) * 0.01
        cost += (self.output_tokens / 1000) * 0.03
        return round(cost, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "calls_per_tool": dict(self.calls_per_tool),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "image_generations": self.image_generations,
            "video_generations": self.video_generations,
            "audio_generations": self.audio_generations,
            "duration_seconds": self.duration_seconds,
            "estimated_cost": self.estimated_cost,
        }


# ═══════════════════ BudgetController ═══════════════════

class BudgetController:
    """统一预算检查与用量记录。"""

    def __init__(self, budget: TaskBudget | None = None):
        self.budget = budget or TaskBudget()
        self.usage = BudgetUsage()

    # ── 记录 ──

    def record_iteration(self) -> None:
        self.usage.iterations += 1

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        self.usage.input_tokens += input_tokens
        self.usage.output_tokens += output_tokens

    def record_tool_call(self, tool_name: str) -> None:
        self.usage.tool_calls += 1
        self.usage.calls_per_tool[tool_name] = self.usage.calls_per_tool.get(tool_name, 0) + 1
        if tool_name in IMAGE_TOOLS:
            self.usage.image_generations += 1
        elif tool_name in VIDEO_TOOLS:
            self.usage.video_generations += 1
        elif tool_name in AUDIO_TOOLS:
            self.usage.audio_generations += 1

    # ── 检查：LLM 轮次前 ──

    def check_iteration(self) -> BudgetDecision:
        pct = self.usage.iterations / self.budget.max_iterations
        if pct >= 1.0:
            return BudgetDecision(
                action=BudgetAction.BLOCK,
                category="iteration",
                message=f"已达最大迭代次数 {self.budget.max_iterations}",
                usage_pct=pct,
            )
        if pct >= self.budget.warn_threshold:
            return BudgetDecision(
                action=BudgetAction.WARN,
                category="iteration",
                message=f"迭代次数 {self.usage.iterations}/{self.budget.max_iterations} ({pct:.0%})",
                usage_pct=pct,
            )
        return BudgetDecision(usage_pct=pct)

    def check_tokens(self) -> BudgetDecision:
        total = self.usage.input_tokens + self.usage.output_tokens
        limit = self.budget.max_input_tokens + self.budget.max_output_tokens
        pct = total / limit if limit > 0 else 0
        if pct >= 1.0:
            return BudgetDecision(
                action=BudgetAction.BLOCK,
                category="token",
                message=f"Token 总量已达预算上限 {limit}",
                usage_pct=pct,
            )
        if pct >= self.budget.warn_threshold:
            return BudgetDecision(
                action=BudgetAction.WARN,
                category="token",
                message=f"Token 使用 {total}/{limit} ({pct:.0%})",
                usage_pct=pct,
            )
        return BudgetDecision(usage_pct=pct)

    # ── 检查：工具调用前 ──

    def check_tool(self, tool_name: str) -> BudgetDecision:
        # 总工具调用数
        total_pct = self.usage.tool_calls / self.budget.max_tool_calls if self.budget.max_tool_calls > 0 else 0
        if total_pct >= 1.0:
            return BudgetDecision(
                action=BudgetAction.BLOCK,
                category="tool",
                message=f"总工具调用已达上限 {self.budget.max_tool_calls}",
                usage_pct=total_pct,
            )

        # 单工具调用数
        current = self.usage.calls_per_tool.get(tool_name, 0)
        limit = self.budget.max_calls_per_tool.get(tool_name, 99)
        if current >= limit:
            return BudgetDecision(
                action=BudgetAction.BLOCK,
                category="tool",
                message=f"工具 {tool_name} 已调用 {current}/{limit} 次，已达上限",
                usage_pct=current / limit,
            )

        # 高成本工具专项预算
        if tool_name in VIDEO_TOOLS:
            v_pct = self.usage.video_generations / self.budget.max_video_generations if self.budget.max_video_generations > 0 else 0
            if v_pct >= 1.0:
                return BudgetDecision(
                    action=BudgetAction.ASK_USER,
                    category="cost",
                    message=f"视频生成次数已达预算上限 {self.budget.max_video_generations}",
                    usage_pct=v_pct,
                )
            if v_pct >= self.budget.warn_threshold:
                return BudgetDecision(
                    action=BudgetAction.WARN,
                    category="cost",
                    message=f"视频生成 {self.usage.video_generations}/{self.budget.max_video_generations}",
                    usage_pct=v_pct,
                )

        if tool_name in IMAGE_TOOLS:
            i_pct = self.usage.image_generations / self.budget.max_image_generations if self.budget.max_image_generations > 0 else 0
            if i_pct >= 1.0:
                return BudgetDecision(
                    action=BudgetAction.ASK_USER,
                    category="cost",
                    message=f"图片生成次数已达预算上限 {self.budget.max_image_generations}",
                    usage_pct=i_pct,
                )

        if tool_name in AUDIO_TOOLS:
            a_pct = self.usage.audio_generations / self.budget.max_audio_generations if self.budget.max_audio_generations > 0 else 0
            if a_pct >= 1.0:
                return BudgetDecision(
                    action=BudgetAction.ASK_USER,
                    category="cost",
                    message=f"音频生成次数已达预算上限 {self.budget.max_audio_generations}",
                    usage_pct=a_pct,
                )

        return BudgetDecision(usage_pct=total_pct)

    # ── 检查：持续时间 ──

    def check_duration(self) -> BudgetDecision:
        dur = self.usage.duration_seconds
        pct = dur / self.budget.max_duration_seconds if self.budget.max_duration_seconds > 0 else 0
        if pct >= 1.0:
            return BudgetDecision(
                action=BudgetAction.BLOCK,
                category="duration",
                message=f"任务执行时间已达上限 {self.budget.max_duration_seconds}s",
                usage_pct=pct,
            )
        return BudgetDecision(usage_pct=pct)

    # ── 综合检查（LLM 轮次前调用）──

    def pre_llm_check(self) -> BudgetDecision:
        for chk in (self.check_iteration, self.check_tokens, self.check_duration):
            d = chk()
            if d.action != BudgetAction.ALLOW:
                return d
        return BudgetDecision()

    # ── 综合检查（工具调用前调用）──

    def pre_tool_check(self, tool_name: str) -> BudgetDecision:
        d = self.check_tool(tool_name)
        if d.action != BudgetAction.ALLOW:
            return d
        return self.check_duration()
