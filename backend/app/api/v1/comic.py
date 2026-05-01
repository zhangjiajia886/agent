import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import settings
from app.db.session import get_db, AsyncSessionLocal
from app.models.comic_task import ComicTask, ComicTaskStatus
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.core.comic_agent import comic_agent, ComicRequest

router = APIRouter()


# ──────────────────── Schema ────────────────────

class ComicGenerateResponse(BaseModel):
    task_id: int
    status: str


class ComicTaskDetail(BaseModel):
    task_id: int
    status: str
    description: str
    style: Optional[str]
    num_frames: int
    storyboard: Optional[list]
    prompts: Optional[list]
    frame_urls: Optional[list]
    video_url: Optional[str]
    error_message: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]


# ──────────────────── 辅助函数 ────────────────────

def _comic_upload_dir() -> str:
    path = os.path.join(settings.UPLOAD_DIR, "comic")
    os.makedirs(path, exist_ok=True)
    return path


async def _save_frame(frame_bytes: bytes, task_id: int, index: int) -> str:
    filename = f"comic_{task_id}_frame{index}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(_comic_upload_dir(), filename)
    with open(filepath, "wb") as f:
        f.write(frame_bytes)
    return f"/uploads/comic/{filename}"


async def _save_video(video_bytes: bytes, task_id: int) -> str:
    filename = f"comic_{task_id}_video_{uuid.uuid4().hex[:8]}.mp4"
    filepath = os.path.join(_comic_upload_dir(), filename)
    with open(filepath, "wb") as f:
        f.write(video_bytes)
    return f"/uploads/comic/{filename}"


async def process_comic_task(
    task_id: int,
    description: str,
    face_image: Optional[bytes],
    num_frames: int,
    include_video: bool,
):
    async with AsyncSessionLocal() as db:
        result_row = await db.execute(select(ComicTask).where(ComicTask.id == task_id))
        task = result_row.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = ComicTaskStatus.processing
            await db.commit()

            request = ComicRequest(
                description=description,
                face_image=face_image,
                num_frames=num_frames,
                include_video=include_video,
            )
            result = await comic_agent.generate(request)

            if result.error:
                task.status = ComicTaskStatus.failed
                task.error_message = result.error
            else:
                frame_urls = []
                for i, frame_bytes in enumerate(result.frames):
                    url = await _save_frame(frame_bytes, task_id, i)
                    frame_urls.append(url)

                task.style = result.style
                task.storyboard = result.storyboard
                task.prompts = result.prompts
                task.frame_urls = frame_urls
                task.status = ComicTaskStatus.completed
                task.completed_at = datetime.utcnow()

            await db.commit()
            logger.info(f"ComicTask {task_id} finished: {task.status}")

        except Exception as e:
            logger.error(f"ComicTask {task_id} error: {e}", exc_info=True)
            task.status = ComicTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


# ──────────────────── 路由 ────────────────────

@router.post("/generate", response_model=ComicGenerateResponse)
async def generate_comic(
    background_tasks: BackgroundTasks,
    description: str = Form(..., description="用自然语言描述漫剧内容，例如：仙侠风格4格漫剧，少女初入仙山"),
    num_frames: int = Form(4, ge=1, le=8),
    include_video: bool = Form(False),
    face_image: Optional[UploadFile] = File(None, description="人脸参考图，可选，用于保持人物面部特征"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.COMFYUI_ENABLED:
        raise HTTPException(status_code=503, detail="漫剧生成服务当前未启用")

    face_bytes = None
    face_url = None
    if face_image:
        face_bytes = await face_image.read()
        face_filename = f"face_{uuid.uuid4().hex[:8]}.jpg"
        face_path = os.path.join(_comic_upload_dir(), face_filename)
        with open(face_path, "wb") as f:
            f.write(face_bytes)
        face_url = f"/uploads/comic/{face_filename}"

    task = ComicTask(
        user_id=current_user.id,
        description=description,
        num_frames=num_frames,
        include_video=include_video,
        face_image_url=face_url,
        status=ComicTaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_comic_task,
        task.id, description, face_bytes, num_frames, include_video,
    )

    return ComicGenerateResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks/{task_id}", response_model=ComicTaskDetail)
async def get_comic_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ComicTask).where(ComicTask.id == task_id, ComicTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return ComicTaskDetail(
        task_id=task.id,
        status=task.status.value,
        description=task.description,
        style=task.style,
        num_frames=task.num_frames,
        storyboard=task.storyboard,
        prompts=task.prompts,
        frame_urls=task.frame_urls,
        video_url=task.video_url,
        error_message=task.error_message,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


@router.get("/health")
async def comic_health():
    healthy = await comic_agent.comfyui.check_health()
    return {
        "comfyui_reachable": healthy,
        "comfyui_url": settings.COMFYUI_URL,
        "enabled": settings.COMFYUI_ENABLED,
    }


# ──────────────────── 图像编辑后台任务 ────────────────────

async def process_edit_task(task_id: int, source_image: bytes, instruction: str, seed: int):
    async with AsyncSessionLocal() as db:
        result_row = await db.execute(select(ComicTask).where(ComicTask.id == task_id))
        task = result_row.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = ComicTaskStatus.processing
            await db.commit()

            result = await comic_agent.edit_image(source_image, instruction, seed)

            if result.error:
                task.status = ComicTaskStatus.failed
                task.error_message = result.error
            else:
                frame_urls = []
                for i, frame_bytes in enumerate(result.frames):
                    url = await _save_frame(frame_bytes, task_id, i)
                    frame_urls.append(url)
                task.style = "edit"
                task.frame_urls = frame_urls
                task.status = ComicTaskStatus.completed
                task.completed_at = datetime.utcnow()

            await db.commit()
            logger.info(f"EditTask {task_id} finished: {task.status}")

        except Exception as e:
            logger.error(f"EditTask {task_id} error: {e}", exc_info=True)
            task.status = ComicTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


# ──────────────────── 图生视频后台任务 ────────────────────

async def process_animate_task(task_id: int, source_image: bytes, motion_prompt: str, seed: int):
    async with AsyncSessionLocal() as db:
        result_row = await db.execute(select(ComicTask).where(ComicTask.id == task_id))
        task = result_row.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = ComicTaskStatus.processing
            await db.commit()

            result = await comic_agent.animate_image(source_image, motion_prompt, seed)

            if result.error:
                task.status = ComicTaskStatus.failed
                task.error_message = result.error
            else:
                video_url = await _save_video(result.video, task_id)
                task.style = "animate"
                task.video_url = video_url
                task.status = ComicTaskStatus.completed
                task.completed_at = datetime.utcnow()

            await db.commit()
            logger.info(f"AnimateTask {task_id} finished: {task.status}")

        except Exception as e:
            logger.error(f"AnimateTask {task_id} error: {e}", exc_info=True)
            task.status = ComicTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


# ──────────────────── /edit 路由 ────────────────────

@router.post("/edit", response_model=ComicGenerateResponse)
async def edit_comic_image(
    background_tasks: BackgroundTasks,
    source_image: UploadFile = File(..., description="要编辑的原始图像"),
    instruction: str = Form(..., description="编辑指令，例如：把衬衫改成红色"),
    seed: int = Form(-1, description="随机种子，-1 为随机"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.COMFYUI_ENABLED:
        raise HTTPException(status_code=503, detail="漫剧生成服务当前未启用")

    img_bytes = await source_image.read()

    task = ComicTask(
        user_id=current_user.id,
        description=instruction,
        num_frames=1,
        include_video=False,
        style="edit",
        status=ComicTaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(process_edit_task, task.id, img_bytes, instruction, seed)
    return ComicGenerateResponse(task_id=task.id, status=task.status.value)


# ──────────────────── /animate 路由 ────────────────────

@router.post("/animate", response_model=ComicGenerateResponse)
async def animate_comic_image(
    background_tasks: BackgroundTasks,
    source_image: UploadFile = File(..., description="要动态化的源图像"),
    motion_prompt: str = Form(..., description="运动描述，例如：人物缓缓转头，头发轻轻飘动"),
    seed: int = Form(-1, description="随机种子，-1 为随机"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.COMFYUI_ENABLED:
        raise HTTPException(status_code=503, detail="漫剧生成服务当前未启用")

    img_bytes = await source_image.read()

    task = ComicTask(
        user_id=current_user.id,
        description=motion_prompt,
        num_frames=1,
        include_video=True,
        style="animate",
        status=ComicTaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(process_animate_task, task.id, img_bytes, motion_prompt, seed)
    return ComicGenerateResponse(task_id=task.id, status=task.status.value)
