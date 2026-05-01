"""
P2 TaskPlanner —— 规则模板驱动的结构化 TaskGraph 生成器。

替代 P0 task_runtime.infer_task_steps 的关键词猜测，
生成带 depends_on / output_artifact_types / fallback_tools 的 PlannedStep。

设计模式：Plan-and-Execute（P10 选型）。
实现 TaskPlannerProtocol（P10 接口契约）。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .tool_capability import (
    ToolCapability,
    TOOL_CAPABILITIES,
    get_capability,
    get_fallbacks,
)
from .task_runtime import RuntimeStep, RuntimeTask


# ═══════════════════ PlannedStep ═══════════════════

@dataclass
class PlannedStep:
    step_uid: str
    title: str
    description: str = ""
    tool_name: str | None = None
    depends_on: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    required: bool = True
    output_artifact_types: list[str] = field(default_factory=list)
    fallback_tools: list[str] = field(default_factory=list)
    sort_order: int = 0


def _uid(prefix: str = "step") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ═══════════════════ 规则模板 ═══════════════════

def _detect_intents(user_goal: str) -> dict[str, bool]:
    """从用户目标检测意图集合。"""
    g = user_goal
    return {
        "image": bool(re.search(r"生成|画|图片|图像|漫剧|漫画|插画|封面", g)),
        "edit": bool(re.search(r"编辑|修改|改成|变成|弄成|调整", g)),
        "upscale": bool(re.search(r"高清|超分|放大|清晰", g)),
        "video": bool(re.search(r"视频|动态|动起来|图生视频|动画", g)),
        "tts": bool(re.search(r"旁白|配音|语音|音频|朗读", g)),
        "merge": bool(re.search(r"合成|成片|字幕|完整视频", g)),
        "multi_frame": bool(re.search(r"四格|多格|分镜|\d+格|连环", g)),
    }


def _parse_frames(user_goal: str) -> int:
    """尝试从目标中解析格数。"""
    m = re.search(r"(\d+)\s*格", user_goal)
    if m:
        return max(1, min(int(m.group(1)), 12))
    if re.search(r"四格", user_goal):
        return 4
    return 0


# ═══════════════════ TaskPlanner ═══════════════════

class TaskPlanner:
    """
    规则模板 TaskPlanner。

    根据用户目标检测意图 → 匹配规则模板 → 校验工具可用性 →
    生成带 depends_on 的 PlannedStep 列表 → 转换为 RuntimeTask。
    """

    def __init__(self, enabled_tools: set[str] | None = None):
        self._enabled = enabled_tools  # None = 全部启用

    def _is_tool_available(self, tool_name: str) -> bool:
        if self._enabled is not None:
            return tool_name in self._enabled
        return tool_name in TOOL_CAPABILITIES

    def _resolve_tool(self, preferred: str) -> str | None:
        """返回可用的工具名，优先 preferred，否则尝试 fallback。"""
        if self._is_tool_available(preferred):
            return preferred
        for fb in get_fallbacks(preferred):
            if self._is_tool_available(fb):
                return fb
        return None

    def _make_step(
        self,
        title: str,
        tool_name: str | None,
        *,
        description: str = "",
        depends_on: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        required: bool = True,
        sort_order: int = 0,
    ) -> PlannedStep:
        cap = get_capability(tool_name) if tool_name else None
        return PlannedStep(
            step_uid=_uid(),
            title=title,
            description=description,
            tool_name=tool_name,
            depends_on=depends_on or [],
            inputs=inputs or {},
            required=required,
            output_artifact_types=list(cap.output_artifact_types) if cap else [],
            fallback_tools=list(cap.fallback_tools) if cap else [],
            sort_order=sort_order,
        )

    # ── 核心入口 ──

    def plan(self, user_goal: str, **kwargs: Any) -> list[PlannedStep]:
        """生成 PlannedStep 列表。"""
        intents = _detect_intents(user_goal)
        frames = _parse_frames(user_goal)
        steps: list[PlannedStep] = []
        order = 0

        # ── 多格漫剧模板 ──
        if intents["multi_frame"] or frames >= 2:
            frames = frames or 4
            img_tool = self._resolve_tool("generate_image")
            frame_uids: list[str] = []
            for i in range(1, frames + 1):
                order += 1
                s = self._make_step(
                    title=f"生成第 {i} 格",
                    tool_name=img_tool,
                    description=f"生成第 {i}/{frames} 格分镜图片。",
                    inputs={"frame": i, "total_frames": frames},
                    sort_order=order,
                )
                steps.append(s)
                frame_uids.append(s.step_uid)

            # 合成
            merge_tool = self._resolve_tool("merge_media")
            order += 1
            steps.append(self._make_step(
                title="合成漫剧成片",
                tool_name=merge_tool,
                description="将多格图片合成最终成片。",
                depends_on=list(frame_uids),
                required=True,
                sort_order=order,
            ))
            return steps

        # ── 图片生成 ──
        img_uid: str | None = None
        if intents["image"]:
            img_tool = self._resolve_tool("generate_image")
            order += 1
            s = self._make_step(
                title="生成视觉产物",
                tool_name=img_tool,
                description="根据用户目标生成图片或分镜视觉产物。",
                sort_order=order,
            )
            steps.append(s)
            img_uid = s.step_uid

        # ── 图片编辑 ──
        if intents["edit"]:
            edit_tool = self._resolve_tool("edit_image")
            order += 1
            deps = [img_uid] if img_uid else []
            s = self._make_step(
                title="执行图像编辑",
                tool_name=edit_tool,
                description="根据用户要求调整已有图像。",
                depends_on=deps,
                sort_order=order,
            )
            steps.append(s)
            img_uid = s.step_uid  # 编辑后的图片作为下游输入

        # ── 超分 ──
        if intents["upscale"]:
            up_tool = self._resolve_tool("upscale_image")
            order += 1
            deps = [img_uid] if img_uid else []
            s = self._make_step(
                title="增强图像清晰度",
                tool_name=up_tool,
                description="对图像进行超分或清晰度增强。",
                depends_on=deps,
                sort_order=order,
            )
            steps.append(s)
            img_uid = s.step_uid

        # ── 图生视频 ──
        video_uid: str | None = None
        if intents["video"]:
            vid_tool = self._resolve_tool("image_to_video")
            order += 1
            deps = [img_uid] if img_uid else []
            s = self._make_step(
                title="制作动态视频",
                tool_name=vid_tool,
                description="将图片或视觉产物转化为动态视频。",
                depends_on=deps,
                sort_order=order,
            )
            steps.append(s)
            video_uid = s.step_uid

        # ── TTS ──
        tts_uid: str | None = None
        if intents["tts"]:
            tts_tool = self._resolve_tool("text_to_speech")
            order += 1
            s = self._make_step(
                title="生成旁白音频",
                tool_name=tts_tool,
                description="合成任务所需的旁白或语音。",
                sort_order=order,
            )
            steps.append(s)
            tts_uid = s.step_uid

        # ── 合成 ──
        if intents["merge"] or (video_uid and tts_uid):
            merge_tool = self._resolve_tool("merge_media")
            order += 1
            deps = []
            if video_uid:
                deps.append(video_uid)
            if tts_uid:
                deps.append(tts_uid)
            steps.append(self._make_step(
                title="合成最终媒体",
                tool_name=merge_tool,
                description="合成音视频、字幕或最终成片。",
                depends_on=deps,
                sort_order=order,
            ))

        # ── 无识别意图：通用 step ──
        if not steps:
            order += 1
            steps.append(self._make_step(
                title="执行核心任务",
                tool_name=None,
                description="根据 Agent 判断完成用户本轮请求。",
                sort_order=order,
            ))

        return steps

    # ── 转换为 RuntimeTask ──

    def plan_to_runtime(self, user_goal: str, **kwargs: Any) -> RuntimeTask:
        """Plan-and-Execute：生成 PlannedStep 并转为 RuntimeTask。"""
        planned = self.plan(user_goal, **kwargs)
        task_uid = f"task_{uuid.uuid4().hex[:12]}"
        runtime_steps = []
        for ps in planned:
            rs = RuntimeStep(
                step_uid=ps.step_uid,
                title=ps.title,
                tool_name=ps.tool_name,
                description=ps.description,
                status="pending",
                inputs=ps.inputs,
                depends_on=list(ps.depends_on),
            )
            runtime_steps.append(rs)
        return RuntimeTask(
            task_uid=task_uid,
            user_goal=user_goal,
            steps=runtime_steps,
        )
