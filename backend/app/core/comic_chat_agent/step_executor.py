"""
P3 StepExecutor —— 步骤级 ReAct 执行器。

Scheduler 决定执行哪个 step，StepExecutor 只负责完成当前 step。
LLM 被约束在「单步骤」范围内工作，不允许跳步或自行决定下一步。

设计模式：ReAct / StepExecutor（P10 选型）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .task_runtime import RuntimeStep, RuntimeTask


# ═══════════════════ StepContext ═══════════════════

@dataclass
class StepContext:
    """传递给 LLM 的步骤执行上下文。"""
    step: RuntimeStep
    user_goal: str
    upstream_outputs: dict[str, Any] = field(default_factory=dict)
    available_tools: list[str] = field(default_factory=list)
    conversation_summary: str = ""
    model_name: str = ""


# ═══════════════════ StepExecutor ═══════════════════

class StepExecutor:
    """
    步骤级执行器。

    职责：
    1. 构建步骤执行 Prompt（约束 LLM 只完成当前 step）。
    2. 提供上游产物上下文。
    3. 记录步骤执行摘要。
    """

    # ── 构建步骤 Prompt ──

    @staticmethod
    def build_step_prompt(ctx: StepContext) -> str:
        """构建约束 LLM 只执行当前 step 的系统提示。"""
        lines = [
            "你正在执行 TaskGraph 中的单个步骤。",
            "",
            f"## 当前步骤",
            f"- 标题：{ctx.step.title}",
        ]
        if ctx.step.description:
            lines.append(f"- 描述：{ctx.step.description}")
        if ctx.step.tool_name:
            lines.append(f"- 推荐工具：{ctx.step.tool_name}")
        if ctx.step.inputs:
            lines.append(f"- 已有输入参数：{ctx.step.inputs}")

        lines.append("")
        lines.append(f"## 用户原始目标")
        lines.append(ctx.user_goal)

        if ctx.upstream_outputs:
            lines.append("")
            lines.append("## 上游步骤产出（你可以使用这些资源）")
            for uid, outputs in ctx.upstream_outputs.items():
                lines.append(f"- {uid}: {outputs}")

        lines.extend([
            "",
            "## 约束",
            "- 只能完成当前步骤，不得跳到其他步骤。",
            "- 如果当前步骤需要工具，必须返回 tool_call。",
            "- 如果缺少必要输入（如图片路径），返回说明而不是编造路径。",
            "- 完成后输出简短的步骤执行结果摘要。",
        ])
        return "\n".join(lines)

    # ── 构建步骤工作记忆 ──

    @staticmethod
    def build_step_memory(ctx: StepContext) -> str:
        """构建步骤级工作记忆，注入上游产物。"""
        if not ctx.upstream_outputs:
            return ""
        items = []
        for uid, outputs in ctx.upstream_outputs.items():
            if isinstance(outputs, dict):
                for key, val in outputs.items():
                    if isinstance(val, str) and any(
                        ext in val for ext in (".png", ".jpg", ".mp4", ".wav", ".mp3")
                    ):
                        items.append(f"{key}: {val}")
            elif isinstance(outputs, str):
                items.append(outputs)
        if not items:
            return ""
        return "[上游产物] " + " | ".join(items)

    # ── 判断步骤是否可直接执行（有工具且有必要参数） ──

    @staticmethod
    def can_auto_execute(step: RuntimeStep, upstream_outputs: dict[str, Any]) -> bool:
        """判断步骤是否具备自动执行的条件。"""
        if not step.tool_name:
            return False
        # 需要图片输入的工具，检查上游是否有图片产出
        image_tools = {"image_to_video", "edit_image", "upscale_image", "add_subtitle"}
        if step.tool_name in image_tools:
            has_image = any(
                isinstance(v, dict) and v.get("image_url")
                for v in upstream_outputs.values()
            )
            if not has_image and not step.inputs.get("image_url"):
                return False
        return True

    # ── 提取步骤完成后的产物 ──

    @staticmethod
    def extract_step_outputs(step: RuntimeStep) -> dict[str, Any]:
        """从 step.outputs 中提取有用的产物信息。"""
        outputs = step.outputs or {}
        result: dict[str, Any] = {}
        for key in ("image_url", "video_url", "audio_url", "path", "file_url"):
            if key in outputs:
                result[key] = outputs[key]
        # 从 artifacts 列表中提取
        for art in outputs.get("artifacts", []):
            if isinstance(art, dict):
                for key in ("url", "file_path"):
                    if key in art:
                        result[art.get("artifact_type", "file") + "_url"] = art[key]
        return result
