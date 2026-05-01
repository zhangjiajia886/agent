from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ---- Podcast ----
# 文件字段 (spk1_prompt_audio, spk2_prompt_audio) 通过 UploadFile 传入
# 文本字段通过 Form() 传入

class PodcastResponse(BaseModel):
    task_id: int
    status: str
    model_config = {"from_attributes": True}


# ---- Singer SVS ----
# 所有音频/文件字段通过 UploadFile 传入
# 控制参数通过 Form() 传入

class SVSResponse(BaseModel):
    task_id: int
    status: str
    model_config = {"from_attributes": True}


# ---- Singer SVC ----
# prompt_audio + target_audio 通过 UploadFile 传入
# 高级参数通过 Form() 传入

class SVCResponse(BaseModel):
    task_id: int
    status: str
    model_config = {"from_attributes": True}


# ---- Digital Human ----
# image + audio 通过 UploadFile 传入
# model_type, seed, use_face_crop 通过 Form() 传入

class DigitalHumanResponse(BaseModel):
    task_id: int
    status: str
    model_config = {"from_attributes": True}


# ---- 通用任务详情 ----

class SoulTaskDetail(BaseModel):
    id: int
    task_type: str
    status: str
    input_text: Optional[str] = None
    input_params: Optional[str] = None
    ref_audio_url: Optional[str] = None
    ref_audio2_url: Optional[str] = None
    ref_image_url: Optional[str] = None
    source_audio_url: Optional[str] = None
    output_url: Optional[str] = None
    output_size: Optional[int] = None
    output_format: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
