"""
漫剧 Agent API Pydantic schemas
"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# ──────────── ModelConfig ────────────

class ModelConfigSchema(BaseModel):
    id: int
    name: str
    category: str
    provider: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_id: str
    model_params: Optional[dict] = None
    is_default: bool
    is_enabled: bool

    model_config = {"from_attributes": True}


class ModelConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    model_params: Optional[dict] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_id: Optional[str] = None


# ──────────── ToolRegistry ────────────

class ToolRegistrySchema(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    executor_type: str
    is_enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


class ToolRegistryUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


# ──────────── WorkflowTemplate ────────────

class WorkflowTemplateSchema(BaseModel):
    id: int
    name: str
    display_name: str
    category: str
    style_tag: Optional[str] = None
    test_time: Optional[int] = None
    is_enabled: bool

    model_config = {"from_attributes": True}


class WorkflowTemplateUpdate(BaseModel):
    is_enabled: Optional[bool] = None


# ──────────── Conversation ────────────

class ConversationCreate(BaseModel):
    title: Optional[str] = None


class AgentMessageSchema(BaseModel):
    id: int
    role: str
    content: Optional[str] = None
    tool_calls: Optional[Any] = None
    tool_result: Optional[Any] = None
    attachments: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSchema(BaseModel):
    id: int
    session_id: str
    title: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    messages: List[AgentMessageSchema] = []

    model_config = {"from_attributes": True}


class ConversationListItem(BaseModel):
    id: int
    session_id: str
    title: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────── AgentPrompt ────────────

class AgentPromptSchema(BaseModel):
    id: int
    node_name: str
    display_name: str
    prompt_type: str
    content: str
    description: Optional[str] = None
    sort_order: int
    is_enabled: bool

    model_config = {"from_attributes": True}


class AgentPromptUpdate(BaseModel):
    content: Optional[str] = None
    is_enabled: Optional[bool] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
