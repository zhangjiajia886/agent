from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import os
import uuid
from datetime import datetime

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.asr_task import ASRTask, TaskStatusEnum
from app.schemas.asr import ASRRequest, ASRResponse, ASRTaskDetail
from app.api.v1.auth import get_current_user
from app.core.fish_speech import fish_client
from app.config import settings
from loguru import logger

router = APIRouter()


async def save_uploaded_audio(file: UploadFile) -> str:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "mp3"
    filename = f"{uuid.uuid4()}.{file_extension}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return filepath


async def process_asr_task(
    task_id: int, audio_path: str, language: str,
    filename: str = "audio.mp3", content_type: str = "audio/mpeg"
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ASRTask).where(ASRTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = TaskStatusEnum.processing
            await db.commit()

            with open(audio_path, "rb") as f:
                audio_data = f.read()

            asr_result = await fish_client.recognize_speech(
                audio_data=audio_data,
                language=language,
                ignore_timestamps=False,
                filename=filename,
                content_type=content_type,
            )

            task.recognized_text = asr_result.get("text")
            task.duration = asr_result.get("duration")
            task.segments = asr_result.get("segments")
            task.status = TaskStatusEnum.completed
            task.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"ASR task {task_id} failed: {e}")
            task.status = TaskStatusEnum.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/recognize", response_model=ASRResponse)
async def recognize_speech(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    language: str = "zh",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid audio file")

    actual_filename = audio.filename or "recording.webm"
    actual_content_type = audio.content_type or "audio/webm"

    audio_path = await save_uploaded_audio(audio)

    task = ASRTask(
        user_id=current_user.id,
        audio_url=audio_path,
        language=language,
        status=TaskStatusEnum.pending,
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_asr_task, task.id, audio_path, language,
        actual_filename, actual_content_type
    )

    return ASRResponse(
        task_id=task.id,
        status=task.status.value,
    )


@router.get("/tasks", response_model=List[ASRTaskDetail])
async def get_asr_tasks(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ASRTask)
        .order_by(desc(ASRTask.created_at))
        .offset(skip)
        .limit(limit)
    )
    tasks = result.scalars().all()
    return tasks


@router.get("/tasks/{task_id}", response_model=ASRTaskDetail)
async def get_asr_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ASRTask).where(ASRTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task
