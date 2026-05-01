from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import os
import uuid
import struct
from datetime import datetime

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.tts_task import TTSTask, TaskStatusEnum
from app.models.voice_model import VoiceModel
from app.schemas.tts import TTSRequest, TTSResponse, TTSTaskDetail
from app.api.v1.auth import get_current_user
from app.core.fish_speech import fish_client
from app.config import settings
from loguru import logger

router = APIRouter()


def _fix_wav_header(data: bytes) -> bytes:
    if len(data) < 44 or data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        return data
    buf = bytearray(data)
    struct.pack_into('<I', buf, 4, len(data) - 8)
    data_pos = data.find(b'data', 12)
    if data_pos != -1:
        struct.pack_into('<I', buf, data_pos + 4, len(data) - data_pos - 8)
    return bytes(buf)


async def save_audio_file(audio_data: bytes, format: str) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}.{format}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    
    payload = _fix_wav_header(audio_data) if format == 'wav' else audio_data
    
    with open(filepath, "wb") as f:
        f.write(payload)
    
    return f"/uploads/{filename}"


async def process_tts_task(task_id: int, tts_model: str = "s2-pro", normalize: bool = True, style_prompt: str = ""):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(TTSTask).where(TTSTask.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            return
        
        try:
            task.status = TaskStatusEnum.processing
            await db.commit()
            
            voice_model_id = None
            if task.voice_model_id:
                vm_result = await db.execute(select(VoiceModel).where(VoiceModel.id == task.voice_model_id))
                voice_model = vm_result.scalar_one_or_none()
                if voice_model:
                    voice_model_id = voice_model.fish_model_id
            
            audio_data = await fish_client.synthesize_speech(
                text=task.text,
                reference_id=voice_model_id,
                format=task.format.value,
                latency=task.latency.value,
                streaming=False,
                tts_model=tts_model,
                normalize=normalize,
                style_prompt=style_prompt,
            )
            
            audio_url = await save_audio_file(audio_data, task.format.value)
            
            task.audio_url = audio_url
            task.audio_size = len(audio_data)
            task.status = TaskStatusEnum.completed
            task.completed_at = datetime.utcnow()
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"TTS task {task_id} failed: {e}")
            task.status = TaskStatusEnum.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(
    request: TTSRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    task = TTSTask(
        user_id=current_user.id,
        voice_model_id=request.voice_model_id,
        text=request.text,
        format=request.format,
        latency=request.latency,
        streaming=request.streaming,
        status=TaskStatusEnum.pending,
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    background_tasks.add_task(process_tts_task, task.id, request.tts_model, request.normalize, request.style_prompt or "")
    
    return TTSResponse(
        task_id=task.id,
        status=task.status.value,
    )


@router.get("/tasks", response_model=List[TTSTaskDetail])
async def get_tts_tasks(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TTSTask)
        .order_by(desc(TTSTask.created_at))
        .offset(skip)
        .limit(limit)
    )
    tasks = result.scalars().all()
    return tasks


class EmotionTestRequest(BaseModel):
    text: str
    model: str = "s2-pro"
    reference_id: str = ""
    latency: str = "balanced"
    normalize: bool = True


@router.post("/test-emotion")
async def test_emotion_tts(
    body: EmotionTestRequest,
    _: User = Depends(get_current_user),
):
    """调试端点：登录后直接调用，raw text 不做任何过滤，返回 mp3 音频流"""
    text, model = body.text, body.model
    import httpx
    url = f"{settings.FISH_API_URL}/v1/tts"
    headers = {
        "Authorization": f"Bearer {settings.FISH_API_KEY}",
        "Content-Type": "application/json",
        "model": model,
    }
    payload = {
        "text": text,
        "reference_id": body.reference_id or settings.FISH_DEFAULT_VOICE,
        "format": "mp3",
        "latency": body.latency,
        "normalize": body.normalize,
    }
    logger.info(f"[test-emotion] model={model!r} text={text!r}")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info(f"[test-emotion] status={resp.status_code} size={len(resp.content)}")
            resp.raise_for_status()
            return StreamingResponse(iter([resp.content]), media_type="audio/mpeg")
    except httpx.HTTPStatusError as e:
        logger.error(f"[test-emotion] HTTP {e.response.status_code}: {e.response.text}")
        raise HTTPException(status_code=502, detail=f"Fish Audio error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=TTSTaskDetail)
async def get_tts_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TTSTask).where(TTSTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task
