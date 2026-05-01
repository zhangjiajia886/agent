"""
漫剧 Agent 会话与消息表：agent_conversation, agent_message
独立于现有 chat_sessions / chat_messages，前缀 agent_ 避免冲突。
"""
import enum
from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, DateTime, Enum, JSON, ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ConversationStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deleted = "deleted"


class AgentConversation(Base):
    __tablename__ = "agent_conversation"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, unique=True, comment="前端 UUID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True)
    title = Column(String(200), default=None)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.active, index=True)
    agent_config = Column(JSON, default=None, comment="Agent 配置快照")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship(
        "AgentMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.id",
    )


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool_call = "tool_call"
    tool_result = "tool_result"
    system = "system"


class AgentMessage(Base):
    __tablename__ = "agent_message"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("agent_conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, default=None)
    tool_calls = Column(JSON, default=None, comment="Agent 工具调用")
    tool_result = Column(JSON, default=None, comment="工具返回结果")
    attachments = Column(JSON, default=None, comment="附件路径列表")
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("AgentConversation", back_populates="messages")
