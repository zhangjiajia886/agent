"""
漫剧 Agent Prompt 管理表：agent_prompt
将各节点的 system prompt / user prompt 模板统一存储，前端可视化编辑。
"""
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, Boolean, DateTime,
)
from sqlalchemy.sql import func

from app.db.base import Base


class AgentPrompt(Base):
    __tablename__ = "agent_prompt"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_name = Column(String(100), nullable=False, index=True,
                       comment="节点标识: system / intent_parser / story_planner / prompt_builder / ...")
    display_name = Column(String(200), nullable=False, comment="显示名称")
    prompt_type = Column(String(50), nullable=False, default="system",
                         comment="类型: system / user_template")
    content = Column(Text, nullable=False, comment="Prompt 内容（支持 {变量} 占位符）")
    description = Column(Text, default=None, comment="说明文字：这个 prompt 的作用、可用变量列表")
    sort_order = Column(Integer, default=0)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
