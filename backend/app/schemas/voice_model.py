from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class VoiceModelCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    language: str = Field(default="zh", pattern="^(zh|en)$")
    visibility: str = Field(default="private", pattern="^(private|public)$")


class VoiceModelUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    visibility: Optional[str] = Field(None, pattern="^(private|public)$")


class VoiceModelResponse(BaseModel):
    id: int
    fish_model_id: str
    title: str
    description: Optional[str] = None
    language: str
    visibility: str
    sample_audio_url: Optional[str] = None
    usage_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VoiceModelList(BaseModel):
    total: int
    items: list[VoiceModelResponse]
