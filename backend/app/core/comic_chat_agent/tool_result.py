"""
ToolResult 标准化：兼容旧工具返回并提取媒体产物。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArtifactPayload:
    type: str
    url: str
    file_path: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "url": self.url,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "metadata": self.metadata,
        }


@dataclass
class ToolResult:
    status: str
    tool: str
    tool_call_id: str | None = None
    artifacts: list[ArtifactPayload] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    retryable: bool = False
    fallback_tools: list[str] = field(default_factory=list)
    suggestion: str | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tool": self.tool,
            "tool_call_id": self.tool_call_id,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "data": self.data,
            "error": self.error,
            "retryable": self.retryable,
            "fallback_tools": self.fallback_tools,
            "suggestion": self.suggestion,
            "duration_ms": self.duration_ms,
        }


def _error_payload(raw_result: dict[str, Any]) -> dict[str, Any] | None:
    error = raw_result.get("error")
    if not error and raw_result.get("status") in {"error", "failed"}:
        error = raw_result.get("message") or raw_result.get("detail") or "工具执行失败"
    if not error:
        return None
    if isinstance(error, dict):
        return error
    return {"code": raw_result.get("code") or "TOOL_ERROR", "message": str(error)}


def _artifact_from_legacy(raw_result: dict[str, Any], kind: str) -> ArtifactPayload | None:
    url = raw_result.get(f"{kind}_url")
    path = raw_result.get(f"{kind}_path")
    if not url:
        return None
    mime = {"image": "image/*", "video": "video/*", "audio": "audio/*"}.get(kind)
    return ArtifactPayload(type=kind, url=url, file_path=path, mime_type=mime)


def normalize_tool_result(tool_name: str, raw_result: dict[str, Any] | None, tool_call_id: str | None = None) -> ToolResult:
    result = raw_result or {}
    error = _error_payload(result)
    status = result.get("status") or ("error" if error else "success")
    if status == "failed":
        status = "error"

    artifacts: list[ArtifactPayload] = []
    for kind in ("image", "video", "audio"):
        artifact = _artifact_from_legacy(result, kind)
        if artifact:
            artifacts.append(artifact)

    if result.get("success") and result.get("path") and tool_name in {"write_file", "edit_file", "python_exec"}:
        artifacts.append(ArtifactPayload(type="file", url=result["path"], file_path=result["path"]))
    if result.get("ok") and result.get("path") and tool_name == "edit_file":
        artifacts.append(ArtifactPayload(type="file", url=result["path"], file_path=result["path"]))

    fallback_tools: list[str] = []
    if tool_name == "generate_image":
        fallback_tools = ["jimeng_generate_image"]
    elif tool_name == "image_to_video":
        fallback_tools = ["jimeng_generate_video"]
    elif tool_name == "upscale_image":
        fallback_tools = ["jimeng_upscale_image"]
    elif tool_name == "edit_image":
        fallback_tools = ["jimeng_edit_image"]

    retryable = bool(error and tool_name in {"generate_image", "image_to_video", "text_to_speech", "upscale_image", "edit_image"})

    return ToolResult(
        status=status,
        tool=tool_name,
        tool_call_id=tool_call_id,
        artifacts=artifacts,
        data=result,
        error=error,
        retryable=retryable,
        fallback_tools=fallback_tools if error else [],
        suggestion=result.get("suggestion"),
        duration_ms=result.get("duration_ms"),
    )
