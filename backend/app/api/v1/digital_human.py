"""SoulX-FlashHead 数字人视频生成路由"""

import json
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import DigitalHumanResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.flashhead_client import flashhead_client
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()


async def _save_upload(content: bytes, suffix: str) -> tuple:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath, f"/uploads/{filename}"


async def process_dh_task(
    task_id: int, img_path: str, aud_path: str,
    model_type: str, seed: int, use_face_crop: bool,
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            logger.info(
                f"数字人任务开始处理 task_id={task_id} model_type={model_type} seed={seed} use_face_crop={use_face_crop}"
            )
            task.status = SoulTaskStatus.processing
            await db.commit()
            logger.info(f"数字人任务状态已更新为处理中 task_id={task_id}")

            with open(img_path, "rb") as f:
                img_bytes = f.read()
            with open(aud_path, "rb") as f:
                aud_bytes = f.read()
            logger.info(
                f"数字人任务输入文件读取完成 task_id={task_id} 图片字节数={len(img_bytes)} 音频字节数={len(aud_bytes)}"
            )

            logger.info(f"开始调用 FlashHead 生成视频 task_id={task_id}")
            video_bytes = await flashhead_client.generate_video(
                image_bytes=img_bytes,
                audio_bytes=aud_bytes,
                model_type=model_type,
                seed=seed,
                use_face_crop=use_face_crop,
            )
            logger.info(f"FlashHead 返回视频内容成功 task_id={task_id} 视频字节数={len(video_bytes)}")

            # 保存视频文件
            video_filename = f"{uuid.uuid4()}.mp4"
            video_filepath = os.path.join(settings.UPLOAD_DIR, video_filename)
            with open(video_filepath, "wb") as f:
                f.write(video_bytes)
            logger.info(
                f"数字人任务输出文件保存完成 task_id={task_id} 文件路径={video_filepath}"
            )

            task.output_url = f"/uploads/{video_filename}"
            task.output_size = len(video_bytes)
            task.output_format = "mp4"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()
            logger.info(
                f"数字人任务处理完成 task_id={task_id} output_url={task.output_url} output_size={task.output_size}"
            )

        except Exception as e:
            logger.error(f"数字人任务处理失败 task_id={task_id} 错误={e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/generate", response_model=DigitalHumanResponse)
async def generate_digital_human(
    background_tasks: BackgroundTasks,
    # ---- 核心输入 ----
    image: UploadFile = File(..., description="参考人脸图片 (jpg/png)"),
    audio: UploadFile = File(..., description="驱动音频 (wav/mp3)"),
    # ---- 生成参数 ----
    model_type: str = Form(default="lite",
        description='"lite"（实时级，单4090）或 "pro"（高质量，需双5090）'),
    seed: int = Form(default=9999, description="随机种子"),
    use_face_crop: bool = Form(default=False, description="是否自动裁剪人脸区域"),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成数字人口型同步视频（音频驱动，流式生成）"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    logger.info(
        f"收到数字人生成请求 用户ID={current_user.id} 图片文件={image.filename} 音频文件={audio.filename} model_type={model_type} seed={seed} use_face_crop={use_face_crop}"
    )
    img_content = await image.read()
    aud_content = await audio.read()
    img_path, img_url = await _save_upload(img_content, ".jpg")
    aud_path, aud_url = await _save_upload(aud_content, ".wav")
    logger.info(
        f"数字人输入文件保存完成 图片路径={img_path} 音频路径={aud_path} 图片URL={img_url} 音频URL={aud_url}"
    )

    params = json.dumps({
        "model_type": model_type, "seed": seed, "use_face_crop": use_face_crop,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.digital_human,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_image_url=img_url,
        ref_audio_url=aud_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    logger.info(f"数字人任务记录创建完成 task_id={task.id} status={task.status.value}")

    background_tasks.add_task(
        process_dh_task, task.id, img_path, aud_path, model_type, seed, use_face_crop,
    )
    logger.info(f"数字人后台任务已加入队列 task_id={task.id}")
    return DigitalHumanResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_dh_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(
            SoulTask.task_type == SoulTaskType.digital_human,
        )
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_dh_task(
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
async def digital_human_health():
    """检查 FlashHead Space 是否在线"""
    online = await flashhead_client.health_check()
    return {"space": settings.SOUL_FLASHHEAD_SPACE, "online": online}
