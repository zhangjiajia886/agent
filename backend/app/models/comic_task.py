import enum
from sqlalchemy import Column, BigInteger, String, Text, Integer, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.sql import func
from app.db.base import Base


class ComicTaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ComicTask(Base):
    __tablename__ = "comic_tasks"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    description = Column(Text, nullable=False)
    style = Column(String(32))
    num_frames = Column(Integer, default=4)
    include_video = Column(Boolean, default=False)

    face_image_url = Column(String(255))
    storyboard = Column(JSON)
    prompts = Column(JSON)

    frame_urls = Column(JSON)
    video_url = Column(String(255))

    status = Column(Enum(ComicTaskStatus), default=ComicTaskStatus.pending, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
