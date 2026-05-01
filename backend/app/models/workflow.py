"""
工作流 DAG 引擎数据表：workflow_definitions, workflow_executions, execution_checkpoints
"""
import enum
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Enum, JSON, Index,
)
from sqlalchemy.sql import func

from app.db.base import Base


# ──────────── workflow_definitions ────────────

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False, index=True, comment="工作流名称")
    description = Column(Text, comment="工作流描述")
    definition = Column(JSON, nullable=False, comment="nodes + edges + variables")
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────── workflow_executions ────────────

class ExecutionStatus(str, enum.Enum):
    running = "running"
    done = "done"
    error = "error"
    cancelled = "cancelled"


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(String(64), primary_key=True)
    workflow_id = Column(String(64), nullable=False, index=True, comment="关联 workflow_definitions.id")
    user_id = Column(String(64), default=None, comment="发起用户")
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.running)
    inputs = Column(JSON, default=None, comment="执行输入")
    outputs = Column(JSON, default=None, comment="执行输出")
    node_statuses = Column(JSON, default=None, comment="各节点执行状态")
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), default=None)

    __table_args__ = (
        Index("idx_wf_exec_status", "status"),
    )


# ──────────── execution_checkpoints ────────────

class ExecutionCheckpoint(Base):
    __tablename__ = "execution_checkpoints"

    id = Column(String(64), primary_key=True)
    execution_id = Column(String(64), nullable=False, index=True, comment="关联 workflow_executions.id")
    node_id = Column(String(64), default=None, comment="最后完成的节点")
    state = Column(JSON, default=None, comment="ExecutionContext 快照")
    completed_nodes = Column(JSON, default=None, comment="已完成节点列表")
    checkpoint_at = Column(DateTime(timezone=True), server_default=func.now())
