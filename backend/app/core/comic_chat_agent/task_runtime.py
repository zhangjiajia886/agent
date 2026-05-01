"""
漫剧 Agent P0 任务运行时：内存态 TaskGraph + 标准事件构造。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from .tool_result import ToolResult


@dataclass
class RuntimeStep:
    step_uid: str
    title: str
    tool_name: str | None = None
    description: str | None = None
    status: str = "pending"
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    depends_on: list[str] = field(default_factory=list)


@dataclass
class RuntimeTask:
    task_uid: str
    user_goal: str
    task_type: str = "comic_agent"
    status: str = "running"
    steps: list[RuntimeStep] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    current_step_uid: str | None = None


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def infer_task_steps(user_goal: str) -> list[RuntimeStep]:
    steps: list[RuntimeStep] = []
    if re.search(r"生成|画|图片|图像|漫剧|漫画", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="生成视觉产物", tool_name="generate_image", description="根据用户目标生成图片或分镜视觉产物。"))
    if re.search(r"编辑|修改|改成|变成|弄成", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="执行图像编辑", tool_name="edit_image", description="根据用户要求调整已有图像。"))
    if re.search(r"高清|超分|放大", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="增强图像清晰度", tool_name="upscale_image", description="对图像进行超分或清晰度增强。"))
    if re.search(r"视频|动态|动起来|图生视频", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="制作动态视频", tool_name="image_to_video", description="将图片或视觉产物转化为动态视频。"))
    if re.search(r"旁白|配音|语音|音频", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="生成旁白音频", tool_name="text_to_speech", description="合成任务所需的旁白或语音。"))
    if re.search(r"合成|成片|字幕", user_goal):
        steps.append(RuntimeStep(step_uid=_uid("step"), title="合成最终媒体", tool_name="merge_media", description="合成音视频、字幕或最终成片。"))
    if not steps:
        steps.append(RuntimeStep(step_uid=_uid("step"), title="执行核心任务", description="根据 Agent 判断完成用户本轮请求。"))
    return steps


def create_runtime_task(user_goal: str) -> RuntimeTask:
    return RuntimeTask(task_uid=_uid("task"), user_goal=user_goal, steps=infer_task_steps(user_goal))


def task_created_event(task: RuntimeTask) -> dict[str, Any]:
    return {
        "type": "task_created",
        "task_uid": task.task_uid,
        "task": {
            "id": task.task_uid,
            "task_uid": task.task_uid,
            "title": "漫剧 Agent 任务",
            "user_goal": task.user_goal,
            "task_type": task.task_type,
            "status": task.status,
            "current_step_uid": task.current_step_uid,
        },
        "steps": [step_event_payload(step) for step in task.steps],
    }


def step_event_payload(step: RuntimeStep) -> dict[str, Any]:
    return {
        "id": step.step_uid,
        "step_uid": step.step_uid,
        "title": step.title,
        "description": step.description,
        "tool_name": step.tool_name,
        "tool": step.tool_name,
        "status": step.status,
        "inputs": step.inputs,
        "outputs": step.outputs,
        "error": step.error,
    }


def step_update_event(task: RuntimeTask, step: RuntimeStep) -> dict[str, Any]:
    return {"type": "step_update", "task_uid": task.task_uid, "step_uid": step.step_uid, "step": step_event_payload(step)}


def task_update_event(task: RuntimeTask, message: str | None = None) -> dict[str, Any]:
    return {
        "type": "task_update",
        "task_uid": task.task_uid,
        "status": task.status,
        "current_step_uid": task.current_step_uid,
        "message": message,
    }


def artifact_created_event(task: RuntimeTask, step: RuntimeStep | None, artifact: dict[str, Any]) -> dict[str, Any]:
    return {"type": "artifact_created", "task_uid": task.task_uid, "step_uid": step.step_uid if step else None, "artifact": artifact}


def find_step_for_tool(task: RuntimeTask, tool_name: str) -> RuntimeStep:
    canonical_tool = {
        "jimeng_generate_image": "generate_image",
        "generate_image_with_face": "generate_image",
        "jimeng_edit_image": "edit_image",
        "jimeng_upscale_image": "upscale_image",
        "jimeng_generate_video": "image_to_video",
    }.get(tool_name, tool_name)
    for step in task.steps:
        if step.tool_name == canonical_tool and step.status in {"pending", "ready", "running", "awaiting_approval"}:
            step.tool_name = tool_name
            return step
    step = RuntimeStep(step_uid=_uid("step"), title=f"执行工具：{tool_name}", tool_name=tool_name, description="Agent 动态追加的工具执行步骤。")
    task.steps.append(step)
    return step


def apply_tool_result(task: RuntimeTask, step: RuntimeStep, result: ToolResult) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    step.outputs = result.to_dict()
    if result.status == "success" and not result.error:
        step.status = "succeeded"
        for item in result.to_dict()["artifacts"]:
            artifact = {"artifact_uid": _uid("artifact"), "verified": True, **item}
            task.artifacts.append(artifact)
            events.append(artifact_created_event(task, step, artifact))
    elif result.status == "rejected":
        step.status = "canceled"
        step.error = result.error
    elif result.status == "blocked":
        step.status = "blocked"
        step.error = result.error
    else:
        step.status = "failed"
        step.error = result.error
    events.append(step_update_event(task, step))
    return events


def audit_task(task: RuntimeTask, last_text: str = "") -> dict[str, Any]:
    from .completion_auditor import CompletionAuditor
    return CompletionAuditor().audit_to_dict(task, last_text)


def final_report_event(task: RuntimeTask, audit: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    task.status = audit["status"]
    return {
        "type": "done",
        "task_uid": task.task_uid,
        "status": audit["status"],
        "final_report": {
            "status": audit["status"],
            "summary": audit["reason"],
            "user_goal": task.user_goal,
            "completed_steps": audit["completed_steps"],
            "failed_steps": audit["failed_steps"],
            "blocked_steps": audit["blocked_steps"],
            "remaining_steps": audit["remaining_steps"],
            "artifacts": audit["artifacts"],
        },
        "metadata": metadata,
    }
