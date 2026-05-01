"""
工作流 DAG 引擎 Pydantic schemas
"""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


# ──────────── WorkflowDefinition ────────────

class WorkflowDefinitionSchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    definition: dict
    is_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    definition: dict
    is_enabled: bool = True


class WorkflowDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[dict] = None
    is_enabled: Optional[bool] = None


# ──────────── WorkflowExecution ────────────

class WorkflowExecutionSchema(BaseModel):
    id: str
    workflow_id: str
    user_id: Optional[str] = None
    status: str
    inputs: Optional[dict] = None
    outputs: Optional[dict] = None
    node_statuses: Optional[dict] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkflowExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}
    resume: bool = False


# ──────────── CheckpointInfo ────────────

class CheckpointInfoSchema(BaseModel):
    has_checkpoint: bool = False
    checkpoint_id: Optional[str] = None
    last_node_id: Optional[str] = None
    completed_nodes: list[str] = []
    completed_count: int = 0
    checkpoint_at: Optional[str] = None
