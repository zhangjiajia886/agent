from sqlalchemy import Column, BigInteger, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class AudioFormatEnum(str, enum.Enum):
    mp3 = "mp3"
    wav = "wav"
    pcm = "pcm"
    opus = "opus"


class LatencyEnum(str, enum.Enum):
    normal = "normal"
    balanced = "balanced"
    low = "low"


class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TTSTask(Base):
    __tablename__ = "tts_tasks"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    voice_model_id = Column(BigInteger, ForeignKey("voice_models.id", ondelete="SET NULL"))
    text = Column(Text, nullable=False)
    format = Column(Enum(AudioFormatEnum), default=AudioFormatEnum.mp3)
    latency = Column(Enum(LatencyEnum), default=LatencyEnum.balanced)
    streaming = Column(Boolean, default=False)
    audio_url = Column(String(255))
    audio_size = Column(Integer)
    duration = Column(Float)
    status = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.pending, index=True)
    error_message = Column(Text)
    cost_credits = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
