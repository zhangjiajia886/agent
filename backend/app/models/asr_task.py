from sqlalchemy import Column, BigInteger, String, Text, Float, DateTime, ForeignKey, Enum, Numeric, JSON
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ASRTask(Base):
    __tablename__ = "asr_tasks"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_url = Column(String(255), nullable=False)
    language = Column(String(10), default="zh")
    recognized_text = Column(Text)
    duration = Column(Float)
    segments = Column(JSON)
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.pending, index=True)
    error_message = Column(Text)
    cost_credits = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
