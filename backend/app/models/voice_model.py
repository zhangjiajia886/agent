from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class VisibilityEnum(str, enum.Enum):
    private = "private"
    public = "public"


class VoiceModel(Base):
    __tablename__ = "voice_models"
    
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fish_model_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="zh")
    visibility = Column(Enum(VisibilityEnum), default=VisibilityEnum.private)
    sample_audio_url = Column(String(255))
    usage_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
