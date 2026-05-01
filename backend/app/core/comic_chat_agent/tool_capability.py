"""
P8 工具能力元数据注册表。

为 Planner / Scheduler / Replanner 提供工具输入输出类型、风险等级、
fallback、并行策略、成本等级和超时配置。

当前阶段以代码注册为权威来源；后续可从 DB ToolRegistry.executor_config.capability
加载并覆盖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sandbox import RiskLevel


@dataclass(frozen=True)
class ToolCapability:
    risk_level: RiskLevel = RiskLevel.L1
    requires_approval: bool = False
    auto_mode_allowed: bool = True
    input_artifact_types: tuple[str, ...] = ()
    output_artifact_types: tuple[str, ...] = ()
    fallback_tools: tuple[str, ...] = ()
    supports_batch: bool = False
    supports_parallel: bool = False
    max_parallel: int = 1
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    cost_level: str = "low"       # low / medium / high / very_high
    timeout_seconds: int = 60
    tags: tuple[str, ...] = ()    # 分类标签


# ═══════════════════ 全量能力注册表 ═══════════════════

TOOL_CAPABILITIES: dict[str, ToolCapability] = {
    # ── 创作工具：ComfyUI ──
    "generate_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=(),
        output_artifact_types=("image",),
        fallback_tools=("jimeng_generate_image",),
        required_inputs=("prompt",),
        optional_inputs=("style", "width", "height", "seed"),
        cost_level="medium",
        timeout_seconds=120,
        tags=("visual", "comfyui"),
    ),
    "generate_image_with_face": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        required_inputs=("prompt", "face_image"),
        optional_inputs=("style",),
        cost_level="medium",
        timeout_seconds=180,
        tags=("visual", "comfyui", "face"),
    ),
    "edit_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        fallback_tools=("jimeng_edit_image",),
        required_inputs=("source_image", "instruction"),
        cost_level="medium",
        timeout_seconds=120,
        tags=("visual", "comfyui"),
    ),
    "image_to_video": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("video",),
        fallback_tools=("jimeng_generate_video",),
        required_inputs=("source_image",),
        optional_inputs=("motion_prompt",),
        cost_level="high",
        timeout_seconds=300,
        tags=("motion", "comfyui"),
    ),
    "text_to_video": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=(),
        output_artifact_types=("video",),
        fallback_tools=("jimeng_generate_video",),
        required_inputs=("prompt",),
        optional_inputs=("style",),
        cost_level="high",
        timeout_seconds=300,
        tags=("motion", "comfyui"),
    ),
    "upscale_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        fallback_tools=("jimeng_upscale_image",),
        required_inputs=("source_image",),
        cost_level="medium",
        timeout_seconds=120,
        tags=("visual", "comfyui"),
    ),
    "text_to_speech": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=(),
        output_artifact_types=("audio",),
        required_inputs=("text",),
        optional_inputs=("voice_id", "speed"),
        cost_level="low",
        timeout_seconds=60,
        tags=("audio", "tts"),
    ),
    "merge_media": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("video", "audio"),
        output_artifact_types=("video",),
        required_inputs=("video_url", "audio_url"),
        cost_level="low",
        timeout_seconds=120,
        tags=("composite",),
    ),
    "add_subtitle": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("video",),
        output_artifact_types=("video",),
        required_inputs=("video_url", "subtitle_text"),
        cost_level="low",
        timeout_seconds=60,
        tags=("composite",),
    ),

    # ── 创作工具：即梦 ──
    "jimeng_generate_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=(),
        output_artifact_types=("image",),
        fallback_tools=("generate_image",),
        required_inputs=("prompt",),
        optional_inputs=("width", "height", "seed"),
        cost_level="medium",
        timeout_seconds=60,
        tags=("visual", "jimeng"),
    ),
    "jimeng_reference_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        required_inputs=("source_image", "prompt"),
        cost_level="medium",
        timeout_seconds=60,
        tags=("visual", "jimeng"),
    ),
    "jimeng_edit_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        fallback_tools=("edit_image",),
        required_inputs=("source_image", "instruction"),
        cost_level="medium",
        timeout_seconds=60,
        tags=("visual", "jimeng"),
    ),
    "jimeng_upscale_image": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("image",),
        fallback_tools=("upscale_image",),
        required_inputs=("source_image",),
        cost_level="low",
        timeout_seconds=60,
        tags=("visual", "jimeng"),
    ),
    "jimeng_generate_video": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("video",),
        fallback_tools=("image_to_video",),
        required_inputs=("prompt",),
        optional_inputs=("source_image",),
        cost_level="high",
        timeout_seconds=300,
        tags=("motion", "jimeng"),
    ),
    "jimeng_motion_mimic": ToolCapability(
        risk_level=RiskLevel.L1,
        input_artifact_types=("image",),
        output_artifact_types=("video",),
        required_inputs=("source_image",),
        cost_level="high",
        timeout_seconds=300,
        tags=("motion", "jimeng"),
    ),

    # ── 通用工具：只读 (L0) ──
    "read_file": ToolCapability(
        risk_level=RiskLevel.L0,
        required_inputs=("path",),
        optional_inputs=("offset", "limit"),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "readonly"),
    ),
    "list_dir": ToolCapability(
        risk_level=RiskLevel.L0,
        required_inputs=("path",),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "readonly"),
    ),
    "find_files": ToolCapability(
        risk_level=RiskLevel.L0,
        required_inputs=("pattern",),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "readonly"),
    ),
    "grep_search": ToolCapability(
        risk_level=RiskLevel.L0,
        required_inputs=("query",),
        optional_inputs=("path",),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "readonly"),
    ),
    "web_search": ToolCapability(
        risk_level=RiskLevel.L0,
        required_inputs=("query",),
        cost_level="low",
        timeout_seconds=30,
        tags=("network", "readonly"),
    ),

    # ── 通用工具：写入 / 网络 (L2) ──
    "write_file": ToolCapability(
        risk_level=RiskLevel.L2,
        requires_approval=True,
        required_inputs=("path", "content"),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "write"),
    ),
    "edit_file": ToolCapability(
        risk_level=RiskLevel.L2,
        requires_approval=True,
        required_inputs=("path", "old_string", "new_string"),
        optional_inputs=("replace_all",),
        cost_level="low",
        timeout_seconds=10,
        tags=("filesystem", "write"),
    ),
    "http_request": ToolCapability(
        risk_level=RiskLevel.L2,
        requires_approval=True,
        required_inputs=("url",),
        optional_inputs=("method", "headers", "body"),
        cost_level="low",
        timeout_seconds=30,
        tags=("network", "write"),
    ),
    "web_fetch": ToolCapability(
        risk_level=RiskLevel.L2,
        required_inputs=("url",),
        cost_level="low",
        timeout_seconds=30,
        tags=("network", "readonly"),
    ),

    # ── 通用工具：命令执行 (L3) ──
    "bash": ToolCapability(
        risk_level=RiskLevel.L3,
        requires_approval=True,
        required_inputs=("command",),
        optional_inputs=("working_dir", "timeout"),
        cost_level="low",
        timeout_seconds=30,
        tags=("execution",),
    ),
    "python_exec": ToolCapability(
        risk_level=RiskLevel.L3,
        requires_approval=True,
        required_inputs=("code",),
        cost_level="low",
        timeout_seconds=30,
        tags=("execution",),
    ),
}


# ═══════════════════ 查询辅助 ═══════════════════

def get_capability(tool_name: str) -> ToolCapability | None:
    return TOOL_CAPABILITIES.get(tool_name)


def get_fallbacks(tool_name: str) -> tuple[str, ...]:
    cap = TOOL_CAPABILITIES.get(tool_name)
    return cap.fallback_tools if cap else ()


def get_tools_by_output_type(artifact_type: str) -> list[str]:
    return [
        name for name, cap in TOOL_CAPABILITIES.items()
        if artifact_type in cap.output_artifact_types
    ]


def get_tools_by_tag(tag: str) -> list[str]:
    return [
        name for name, cap in TOOL_CAPABILITIES.items()
        if tag in cap.tags
    ]


def get_enabled_tools(tool_names: set[str] | None = None) -> dict[str, ToolCapability]:
    if tool_names is None:
        return dict(TOOL_CAPABILITIES)
    return {k: v for k, v in TOOL_CAPABILITIES.items() if k in tool_names}
