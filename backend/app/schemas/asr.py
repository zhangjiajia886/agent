from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class ASRRequest(BaseModel):
    language: str = Field(default="zh", pattern="^(zh|en|auto)$")
    ignore_timestamps: bool = False


class ASRSegment(BaseModel):
    text: str
    start: float
    end: float


class ASRResponse(BaseModel):
    task_id: int
    text: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
    cost_credits: Optional[Decimal] = None
    status: str
    
    class Config:
        from_attributes = True


class ASRTaskDetail(BaseModel):
    id: int
    audio_url: str
    language: str
    recognized_text: Optional[str] = None
    duration: Optional[float] = None
    segments: Optional[List[Dict[str, Any]]] = None
    status: str
    error_message: Optional[str] = None
    cost_credits: Optional[Decimal] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
