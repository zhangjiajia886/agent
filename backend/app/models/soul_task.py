"""Soul AI Lab 扩展功能的统一异步任务模型"""

from sqlalchemy import (
    Column, BigInteger, String, Text, Integer,
    DateTime, ForeignKey, Enum,
)
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class SoulTaskType(str, enum.Enum):
    podcast = "podcast"        # 播客语音合成
    singing_svs = "singing_svs"  # 歌声合成
    singing_svc = "singing_svc"  # 歌声转换
    digital_human = "digital_human"  # 数字人视频


class SoulTaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class SoulTask(Base):
    __tablename__ = "soul_tasks"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    task_type = Column(Enum(SoulTaskType), nullable=False, index=True)
    status = Column(Enum(SoulTaskStatus), default=SoulTaskStatus.pending, index=True)

    # 输入参数 (JSON 序列化存储)
    input_text = Column(Text)              # 文本/歌词
    input_params = Column(Text)            # JSON: dialect, control_mode 等

    # 输入文件
    ref_audio_url = Column(String(255))    # 说话人1/Prompt 参考音频
    ref_audio2_url = Column(String(255))   # 说话人2 参考音频 (Podcast 双人)
    ref_image_url = Column(String(255))    # 参考图片 (数字人)
    source_audio_url = Column(String(255)) # 目标/源音频 (Singer target_audio / SVC)
    midi_url = Column(String(255))         # MIDI 文件
    metadata_url = Column(String(255))     # metadata JSON 文件 (Singer)

    # 输出
    output_url = Column(String(255))       # 生成结果文件 URL
    output_size = Column(Integer)          # 文件大小 bytes
    output_format = Column(String(10))     # wav / mp4

    # 状态
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
