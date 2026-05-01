"""SoulX-Podcast 播客语音合成路由"""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import PodcastResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.podcast_client import podcast_client
from app.api.v1.tts import save_audio_file
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()


async def _save_upload(content: bytes, suffix: str) -> tuple:
    """保存上传文件，返回 (filepath, url)"""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath, f"/uploads/{filename}"


async def process_podcast_task(
    task_id: int,
    target_text: str,
    spk1_audio_path: str,
    spk1_prompt_text: str,
    spk1_dialect_prompt_text: str,
    spk2_audio_path: Optional[str],
    spk2_prompt_text: str,
    spk2_dialect_prompt_text: str,
    seed: int,
):
    """后台执行播客语音合成"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(spk1_audio_path, "rb") as f:
                spk1_bytes = f.read()
            spk2_bytes = None
            if spk2_audio_path:
                with open(spk2_audio_path, "rb") as f:
                    spk2_bytes = f.read()

            audio_bytes = await podcast_client.synthesize(
                target_text=target_text,
                spk1_prompt_audio_bytes=spk1_bytes,
                spk1_prompt_text=spk1_prompt_text,
                spk1_dialect_prompt_text=spk1_dialect_prompt_text,
                spk2_prompt_audio_bytes=spk2_bytes,
                spk2_prompt_text=spk2_prompt_text,
                spk2_dialect_prompt_text=spk2_dialect_prompt_text,
                seed=seed,
            )

            audio_url = await save_audio_file(audio_bytes, "wav")
            task.output_url = audio_url
            task.output_size = len(audio_bytes)
            task.output_format = "wav"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Podcast task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/synthesize", response_model=PodcastResponse)
async def synthesize_podcast(
    background_tasks: BackgroundTasks,
    # ---- 对话文本 ----
    target_text: str = Form(..., min_length=1, max_length=10000,
        description='对话文本，格式 "[S1]xxx\\n[S2]xxx"，支持 [S1]~[S4]'),
    # ---- 说话人1 ----
    spk1_prompt_audio: UploadFile = File(..., description="说话人1 参考音频"),
    spk1_prompt_text: str = Form(default="", description="说话人1 参考文本（对应音频的文字内容）"),
    spk1_dialect_prompt_text: str = Form(default="",
        description='说话人1 方言提示，如 "<|Sichuan|>四川话文本"'),
    # ---- 说话人2（可选，独白可不传）----
    spk2_prompt_audio: Optional[UploadFile] = File(None, description="说话人2 参考音频"),
    spk2_prompt_text: str = Form(default="", description="说话人2 参考文本"),
    spk2_dialect_prompt_text: str = Form(default="",
        description='说话人2 方言提示'),
    # ---- 控制参数 ----
    seed: int = Form(default=1988, description="随机种子"),
    # ---- 鉴权 & DB ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交播客语音合成任务（支持双说话人独立配置）"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    # 保存说话人1 音频
    spk1_content = await spk1_prompt_audio.read()
    spk1_path, spk1_url = await _save_upload(spk1_content, ".wav")

    # 保存说话人2 音频（可选）
    spk2_path, spk2_url = None, None
    if spk2_prompt_audio:
        spk2_content = await spk2_prompt_audio.read()
        spk2_path, spk2_url = await _save_upload(spk2_content, ".wav")

    params = json.dumps({
        "spk1_prompt_text": spk1_prompt_text,
        "spk1_dialect_prompt_text": spk1_dialect_prompt_text,
        "spk2_prompt_text": spk2_prompt_text,
        "spk2_dialect_prompt_text": spk2_dialect_prompt_text,
        "seed": seed,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.podcast,
        status=SoulTaskStatus.pending,
        input_text=target_text,
        input_params=params,
        ref_audio_url=spk1_url,
        ref_audio2_url=spk2_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_podcast_task, task.id, target_text,
        spk1_path, spk1_prompt_text, spk1_dialect_prompt_text,
        spk2_path, spk2_prompt_text, spk2_dialect_prompt_text, seed,
    )
    return PodcastResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_podcast_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(SoulTask.task_type == SoulTaskType.podcast)
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_podcast_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask).where(SoulTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/health")
async def podcast_health():
    """检查 Podcast Space 是否在线"""
    online = await podcast_client.health_check()
    return {"space": settings.SOUL_PODCAST_SPACE, "online": online}
