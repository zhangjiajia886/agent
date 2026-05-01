"""
漫剧 Agent 配置表：model_config, tool_registry, workflow_template
"""
import enum
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, Boolean, DateTime, Enum, JSON,
)
from sqlalchemy.sql import func

from app.db.base import Base


# ──────────── model_config ────────────

class ModelCategory(str, enum.Enum):
    agent_brain = "agent_brain"
    l1_llm = "l1_llm"
    multimodal = "multimodal"
    embedding = "embedding"
    generation = "generation"


class ModelConfig(Base):
    __tablename__ = "model_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="模型名称")
    category = Column(Enum(ModelCategory), nullable=False, index=True)
    provider = Column(String(50), nullable=False, comment="aipro/southgrid/comfyui/local")
    base_url = Column(String(500), nullable=False, default="")
    api_key = Column(String(500), default=None, comment="加密存储")
    extra_auth = Column(JSON, default=None, comment='{"custcode":"..."}')
    model_id = Column(String(200), nullable=False, comment="模型标识符")
    embedding_dim = Column(Integer, default=None)
    model_params = Column(JSON, default=None, comment='{"max_tokens":4096,"temperature":0.7}')
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────── tool_registry ────────────

class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="工具唯一名")
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, comment="给 Agent 看的描述")
    input_schema = Column(JSON, nullable=False, comment="JSON Schema")
    executor_type = Column(String(50), nullable=False, comment="comfyui/http/local/tts")
    executor_config = Column(JSON, default=None, comment='{"timeout":300}')
    is_enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ──────────── workflow_template ────────────

class WorkflowCategory(str, enum.Enum):
    t2i = "t2i"
    i2v = "i2v"
    t2v = "t2v"
    edit = "edit"
    face = "face"
    upscale = "upscale"
    audio = "audio"


class WorkflowTemplate(Base):
    __tablename__ = "workflow_template"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="工作流标识名")
    display_name = Column(String(200), nullable=False)
    category = Column(Enum(WorkflowCategory), nullable=False, index=True)
    workflow_json = Column(JSON, default=None, comment="ComfyUI workflow JSON (V2)")
    param_mapping = Column(JSON, default=None, comment="参数映射")
    style_tag = Column(String(50), default=None)
    description = Column(Text, default=None)
    test_time = Column(Integer, default=None, comment="测试耗时(秒*10)")
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
