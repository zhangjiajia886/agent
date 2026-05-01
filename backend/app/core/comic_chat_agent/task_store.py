"""
AgentTaskStore —— P1 最小持久化层。

采用短事务写入 AgentTask / AgentStep / AgentEvent / ToolInvocation / AgentArtifact，
避免 WebSocket 长连接持有长事务。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.agent_task import (
    AgentArtifact,
    AgentEvent,
    AgentStep,
    AgentStepStatus,
    AgentTask,
    AgentTaskStatus,
    ToolInvocation,
)

from .task_runtime import RuntimeStep, RuntimeTask
from .tool_result import ToolResult


_STRUCTURED_EVENT_TYPES = {
    "task_created",
    "task_update",
    "step_update",
    "tool_start",
    "tool_done",
    "tool_confirm",
    "artifact_created",
    "incomplete",
    "done",
    "error",
}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task_status(status: str) -> AgentTaskStatus:
    if status == "succeeded":
        return AgentTaskStatus.completed
    return AgentTaskStatus(status) if status in AgentTaskStatus._value2member_map_ else AgentTaskStatus.running


def _step_status(status: str) -> AgentStepStatus:
    return AgentStepStatus(status) if status in AgentStepStatus._value2member_map_ else AgentStepStatus.pending


class AgentTaskStore:
    async def create_task(
        self,
        task: RuntimeTask,
        *,
        conversation_id: int,
        user_id: int | None,
        model_id: str | None,
        auto_mode: bool,
    ) -> None:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(AgentTask).where(AgentTask.task_uid == task.task_uid))
            if existing.scalar_one_or_none():
                return
            db.add(AgentTask(
                task_uid=task.task_uid,
                conversation_id=conversation_id,
                user_id=user_id,
                user_goal=task.user_goal,
                task_type=task.task_type,
                status=_task_status(task.status),
                current_step_uid=task.current_step_uid,
                model_id=model_id,
                auto_mode=auto_mode,
                metadata_json={"source": "agent_runner_p1"},
            ))
            await db.commit()

    async def create_steps(self, task: RuntimeTask) -> None:
        async with AsyncSessionLocal() as db:
            for index, step in enumerate(task.steps):
                existing = await db.execute(select(AgentStep).where(AgentStep.step_uid == step.step_uid))
                if existing.scalar_one_or_none():
                    continue
                db.add(AgentStep(
                    step_uid=step.step_uid,
                    task_uid=task.task_uid,
                    title=step.title,
                    description=step.description,
                    tool_name=step.tool_name,
                    status=_step_status(step.status),
                    inputs=step.inputs or None,
                    outputs=step.outputs or None,
                    error=step.error,
                    sort_order=index,
                ))
            await db.commit()

    async def update_task(self, task: RuntimeTask, final_report: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AgentTask).where(AgentTask.task_uid == task.task_uid))
            row = result.scalar_one_or_none()
            if not row:
                return
            row.status = _task_status(task.status)
            row.current_step_uid = task.current_step_uid
            if final_report is not None:
                row.final_report = final_report
            if error is not None:
                row.error = error
            if row.status in {AgentTaskStatus.completed, AgentTaskStatus.failed, AgentTaskStatus.blocked, AgentTaskStatus.incomplete, AgentTaskStatus.canceled}:
                row.finished_at = row.finished_at or _now()
            await db.commit()

    async def update_step(self, task_uid: str, step: RuntimeStep) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AgentStep).where(AgentStep.step_uid == step.step_uid))
            row = result.scalar_one_or_none()
            if not row:
                row = AgentStep(step_uid=step.step_uid, task_uid=task_uid, title=step.title)
                db.add(row)
            row.title = step.title
            row.description = step.description
            row.tool_name = step.tool_name
            row.status = _step_status(step.status)
            row.inputs = step.inputs or None
            row.outputs = step.outputs or None
            row.error = step.error
            if row.status in {AgentStepStatus.running, AgentStepStatus.awaiting_approval}:
                row.started_at = row.started_at or _now()
            if row.status in {AgentStepStatus.succeeded, AgentStepStatus.failed, AgentStepStatus.blocked, AgentStepStatus.skipped, AgentStepStatus.canceled}:
                row.finished_at = row.finished_at or _now()
            await db.commit()

    async def append_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type not in _STRUCTURED_EVENT_TYPES:
            return
        async with AsyncSessionLocal() as db:
            db.add(AgentEvent(
                event_uid=_uid("event"),
                task_uid=event.get("task_uid"),
                step_uid=event.get("step_uid"),
                event_type=event_type,
                payload=event,
            ))
            await db.commit()

    async def start_tool_invocation(self, task_uid: str, step_uid: str | None, tool_call_id: str | None, tool_name: str, input_data: dict[str, Any]) -> None:
        async with AsyncSessionLocal() as db:
            existing = None
            if tool_call_id:
                result = await db.execute(select(ToolInvocation).where(ToolInvocation.tool_call_id == tool_call_id))
                existing = result.scalar_one_or_none()
            if existing:
                return
            db.add(ToolInvocation(
                invocation_uid=_uid("invoke"),
                task_uid=task_uid,
                step_uid=step_uid,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                input=input_data,
                status="running",
                started_at=_now(),
            ))
            await db.commit()

    async def finish_tool_invocation(self, tool_call_id: str | None, tool_name: str, output: dict[str, Any], result: ToolResult) -> None:
        async with AsyncSessionLocal() as db:
            row = None
            if tool_call_id:
                query_result = await db.execute(select(ToolInvocation).where(ToolInvocation.tool_call_id == tool_call_id))
                row = query_result.scalar_one_or_none()
            if not row:
                logger.warning(f"[AgentTaskStore] tool invocation not found: {tool_name} {tool_call_id}")
                return
            row.output = output
            row.status = result.status
            row.error = result.error
            row.finished_at = _now()
            await db.commit()

    async def create_artifact(self, task_uid: str, step_uid: str | None, artifact: dict[str, Any]) -> None:
        artifact_uid = artifact.get("artifact_uid") or _uid("artifact")
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(AgentArtifact).where(AgentArtifact.artifact_uid == artifact_uid))
            if existing.scalar_one_or_none():
                return
            db.add(AgentArtifact(
                artifact_uid=artifact_uid,
                task_uid=task_uid,
                step_uid=step_uid,
                artifact_type=artifact.get("type") or artifact.get("artifact_type") or "file",
                title=artifact.get("title"),
                url=artifact.get("url") or artifact.get("file_path") or "",
                file_path=artifact.get("file_path"),
                mime_type=artifact.get("mime_type"),
                size_bytes=artifact.get("size_bytes"),
                verified=bool(artifact.get("verified", False)),
                metadata_json=artifact,
            ))
            await db.commit()
