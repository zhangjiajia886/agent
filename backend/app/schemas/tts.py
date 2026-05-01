from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_model_id: Optional[int] = None
    format: str = Field(default="mp3", pattern="^(mp3|wav|pcm|opus)$")
    latency: str = Field(default="balanced", pattern="^(normal|balanced|low)$")
    streaming: bool = False
    mp3_bitrate: Optional[int] = Field(default=128, ge=64, le=192)
    sample_rate: Optional[int] = Field(default=44100, ge=8000, le=48000)
    tts_model: str = Field(default="s2-pro", pattern="^(s1|s2|s2-pro)$")
    normalize: bool = True
    style_prompt: Optional[str] = Field(default=None, max_length=200)


class TTSResponse(BaseModel):
    task_id: int
    audio_url: Optional[str] = None
    duration: Optional[float] = None
    size: Optional[int] = None
    cost_credits: Optional[Decimal] = None
    status: str
    
    class Config:
        from_attributes = True


class TTSTaskDetail(BaseModel):
    id: int
    text: str
    format: str
    latency: str
    streaming: bool
    audio_url: Optional[str] = None
    audio_size: Optional[int] = None
    duration: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    cost_credits: Optional[Decimal] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
