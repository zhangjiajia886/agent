from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ChatMessageSchema(BaseModel):
    id: int
    role: str
    content: str
    tts_audio_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionCreate(BaseModel):
    title: str = "新对话"
    system_prompt: Optional[str] = None


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None


class ChatSessionSchema(BaseModel):
    id: int
    title: str
    system_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageSchema] = []

    model_config = {"from_attributes": True}


class ChatSessionListItem(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: int
    message: str
    with_tts: bool = False
    voice_model_id: Optional[int] = None
