"""
漫剧 Agent 任务状态表：agent_task / agent_step / agent_artifact / agent_event / tool_invocation。
"""
import enum
from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.sql import func

from app.db.base import Base


class AgentTaskStatus(str, enum.Enum):
    created = "created"
    planning = "planning"
    running = "running"
    awaiting_approval = "awaiting_approval"
    incomplete = "incomplete"
    blocked = "blocked"
    failed = "failed"
    canceled = "canceled"
    completed = "completed"


class AgentStepStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    running = "running"
    awaiting_approval = "awaiting_approval"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"
    canceled = "canceled"


class AgentTask(Base):
    __tablename__ = "agent_task"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_uid = Column(String(64), nullable=False, unique=True, index=True)
    conversation_id = Column(BigInteger, ForeignKey("agent_conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True)
    user_goal = Column(Text, nullable=False)
    task_type = Column(String(64), nullable=False, default="comic_agent")
    status = Column(Enum(AgentTaskStatus), nullable=False, default=AgentTaskStatus.created, index=True)
    current_step_uid = Column(String(64), default=None, index=True)
    model_id = Column(String(128), default=None)
    auto_mode = Column(Boolean, default=False)
    final_report = Column(JSON, default=None)
    error = Column(JSON, default=None)
    metadata_json = Column(JSON, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    finished_at = Column(DateTime(timezone=True), default=None)


class AgentStep(Base):
    __tablename__ = "agent_step"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    step_uid = Column(String(64), nullable=False, unique=True, index=True)
    task_uid = Column(String(64), nullable=False, index=True)
    parent_step_uid = Column(String(64), default=None, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default=None)
    step_type = Column(String(64), nullable=False, default="tool")
    tool_name = Column(String(128), default=None, index=True)
    status = Column(Enum(AgentStepStatus), nullable=False, default=AgentStepStatus.pending, index=True)
    depends_on = Column(JSON, default=None)
    inputs = Column(JSON, default=None)
    outputs = Column(JSON, default=None)
    error = Column(JSON, default=None)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), default=None)
    finished_at = Column(DateTime(timezone=True), default=None)


class AgentArtifact(Base):
    __tablename__ = "agent_artifact"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    artifact_uid = Column(String(64), nullable=False, unique=True, index=True)
    task_uid = Column(String(64), nullable=False, index=True)
    step_uid = Column(String(64), default=None, index=True)
    artifact_type = Column(String(32), nullable=False, index=True)
    title = Column(String(255), default=None)
    url = Column(Text, nullable=False)
    file_path = Column(Text, default=None)
    mime_type = Column(String(128), default=None)
    size_bytes = Column(BigInteger, default=None)
    verified = Column(Boolean, default=False)
    metadata_json = Column(JSON, default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AgentEvent(Base):
    __tablename__ = "agent_event"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_uid = Column(String(64), nullable=False, unique=True, index=True)
    task_uid = Column(String(64), default=None, index=True)
    step_uid = Column(String(64), default=None, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ToolInvocation(Base):
    __tablename__ = "tool_invocation"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invocation_uid = Column(String(64), nullable=False, unique=True, index=True)
    task_uid = Column(String(64), nullable=False, index=True)
    step_uid = Column(String(64), default=None, index=True)
    tool_call_id = Column(String(128), default=None, index=True)
    tool_name = Column(String(128), nullable=False, index=True)
    input = Column(JSON, default=None)
    output = Column(JSON, default=None)
    status = Column(String(32), nullable=False, default="running", index=True)
    error = Column(JSON, default=None)
    started_at = Column(DateTime(timezone=True), default=None)
    finished_at = Column(DateTime(timezone=True), default=None)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
