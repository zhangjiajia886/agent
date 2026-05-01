"""SoulX-Singer 歌声合成 + 歌声转换路由"""

import json
import os
import socket
import uuid
import base64
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.soul_task import SoulTask, SoulTaskType, SoulTaskStatus
from app.schemas.soul import SVSResponse, SVCResponse, SoulTaskDetail
from app.api.v1.auth import get_current_user
from app.core.singer_client import singer_client
from app.api.v1.tts import save_audio_file
from app.config import settings
from loguru import logger
from datetime import datetime

router = APIRouter()

_SINGER_LOCAL_PORT = 7862


def _singer_tunnel_up() -> bool:
    """检查 Singer SSH 隧道本地端口是否监听"""
    try:
        s = socket.create_connection(("127.0.0.1", _SINGER_LOCAL_PORT), timeout=2)
        s.close()
        return True
    except OSError:
        return False


async def _singer_preflight():
    """前置检查：先判断隧道，再判断服务，返回明确错误"""
    if not _singer_tunnel_up():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Singer SSH 隧道未建立（本地 127.0.0.1:{_SINGER_LOCAL_PORT} 无监听），"
                "请执行: ssh -CNg -L 7862:127.0.0.1:6006 autodl-singer"
            ),
        )
    if not await singer_client.health_check():
        raise HTTPException(
            status_code=503,
            detail=(
                "隧道已建立但 Singer 服务未在远端启动，"
                "请登录 autodl-singer 执行: "
                "nohup bash -c 'source ~/miniconda3/etc/profile.d/conda.sh && "
                "conda activate /root/autodl-tmp/envs/env-singer && "
                "cd ~/services/singer && "
                "PYTHONUNBUFFERED=1 GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=6006 "
                "python -u webui.py --port 6006' "
                "> ~/logs/singer.log 2>&1 &"
            ),
        )


async def _save_upload(file: UploadFile, suffix: str) -> tuple:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}{suffix}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    return filepath, f"/uploads/{filename}"


async def process_svs_task(
    task_id: int,
    prompt_path: str, target_path: str,
    control: str, auto_shift: bool, pitch_shift: int, seed: int,
    prompt_lyric_lang: str, target_lyric_lang: str,
    prompt_vocal_sep: bool, target_vocal_sep: bool,
    prompt_meta_path: Optional[str], target_meta_path: Optional[str],
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()
            logger.info(f"[SVS task={task_id}] 状态已置为 processing")

            logger.info(f"[SVS task={task_id}] 读取音频文件 prompt={prompt_path} target={target_path}")
            with open(prompt_path, "rb") as f:
                prompt_bytes = f.read()
            with open(target_path, "rb") as f:
                target_bytes = f.read()
            prompt_meta_bytes = open(prompt_meta_path, "rb").read() if prompt_meta_path else None
            target_meta_bytes = open(target_meta_path, "rb").read() if target_meta_path else None
            logger.info(
                f"[SVS task={task_id}] 文件读取完成 "
                f"prompt_audio={len(prompt_bytes)}B target_audio={len(target_bytes)}B "
                f"prompt_meta={'有' if prompt_meta_bytes else '无'} "
                f"target_meta={'有' if target_meta_bytes else '无'}"
            )

            logger.info(
                f"[SVS task={task_id}] 调用 synthesize_singing "
                f"control={control} auto_shift={auto_shift} pitch_shift={pitch_shift} "
                f"seed={seed} prompt_lang={prompt_lyric_lang} target_lang={target_lyric_lang}"
            )
            audio_bytes = await singer_client.synthesize_singing(
                prompt_audio_bytes=prompt_bytes,
                target_audio_bytes=target_bytes,
                control=control,
                auto_shift=auto_shift,
                pitch_shift=pitch_shift,
                seed=seed,
                prompt_lyric_lang=prompt_lyric_lang,
                target_lyric_lang=target_lyric_lang,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
                prompt_metadata_bytes=prompt_meta_bytes,
                target_metadata_bytes=target_meta_bytes,
            )
            logger.info(f"[SVS task={task_id}] 合成成功 output_size={len(audio_bytes)}B")

            audio_url = await save_audio_file(audio_bytes, "wav")
            task.output_url = audio_url
            task.output_size = len(audio_bytes)
            task.output_format = "wav"
            task.status = SoulTaskStatus.completed
            task.completed_at = datetime.utcnow()
            await db.commit()
            logger.info(f"[SVS task={task_id}] 完成 output_url={audio_url}")
        except Exception as e:
            logger.error(f"[SVS task={task_id}] 失败 阶段未知 error={e}", exc_info=True)
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


async def process_svc_task(
    task_id: int,
    prompt_path: str, target_path: str,
    prompt_vocal_sep: bool, target_vocal_sep: bool,
    auto_shift: bool, auto_mix_acc: bool, pitch_shift: int,
    n_step: int, cfg: float, use_fp16: bool, seed: int,
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SoulTask).where(SoulTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            task.status = SoulTaskStatus.processing
            await db.commit()

            with open(prompt_path, "rb") as f:
                prompt_bytes = f.read()
            with open(target_path, "rb") as f:
                target_bytes = f.read()

            audio_bytes = await singer_client.convert_voice(
                prompt_audio_bytes=prompt_bytes,
                target_audio_bytes=target_bytes,
                prompt_vocal_sep=prompt_vocal_sep,
                target_vocal_sep=target_vocal_sep,
                auto_shift=auto_shift,
                auto_mix_acc=auto_mix_acc,
                pitch_shift=pitch_shift,
                n_step=n_step,
                cfg=cfg,
                use_fp16=use_fp16,
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
            logger.error(f"SVC task {task_id} failed: {e}")
            task.status = SoulTaskStatus.failed
            task.error_message = str(e)
            await db.commit()


@router.post("/transcribe")
async def singing_transcription(
    prompt_audio: UploadFile = File(..., description="参考歌手音频"),
    target_audio: UploadFile = File(..., description="目标音频"),
    prompt_lyric_lang: str = Form(default="Mandarin"),
    target_lyric_lang: str = Form(default="Mandarin"),
    prompt_vocal_sep: bool = Form(default=False),
    target_vocal_sep: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    歌词转写（独立预处理步骤）
    返回自动转写的 metadata JSON，用户可下载编辑后再上传到 /svs 精确合成。
    注意：这是同步接口，不走后台任务（转写耗时较短）。
    """
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    prompt_content = await prompt_audio.read()
    target_content = await target_audio.read()

    await _singer_preflight()

    try:
        prompt_meta, target_meta = await singer_client.transcribe(
            prompt_audio_bytes=prompt_content,
            target_audio_bytes=target_content,
            prompt_lyric_lang=prompt_lyric_lang,
            target_lyric_lang=target_lyric_lang,
            prompt_vocal_sep=prompt_vocal_sep,
            target_vocal_sep=target_vocal_sep,
        )
    except Exception as e:
        logger.error(f"Singer transcribe 失败: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Singer transcribe 调用失败: {e}",
        )

    return JSONResponse({
        "prompt_metadata": base64.b64encode(prompt_meta).decode() if prompt_meta else None,
        "target_metadata": base64.b64encode(target_meta).decode() if target_meta else None,
    })


@router.post("/svs", response_model=SVSResponse)
async def singing_voice_synthesis(
    background_tasks: BackgroundTasks,
    # ---- 两段音频（核心输入）----
    prompt_audio: UploadFile = File(..., description="参考歌手音频（目标音色，max 30s）"),
    target_audio: UploadFile = File(..., description="旋律/歌词来源音频（max 60s）"),
    # ---- 控制参数 ----
    control: str = Form(default="melody", description='"melody"(F0旋律) 或 "score"(MIDI乐谱)'),
    auto_shift: bool = Form(default=True, description="自动音高偏移"),
    pitch_shift: int = Form(default=0, ge=-36, le=36, description="手动音高偏移（半音）"),
    seed: int = Form(default=12306),
    prompt_lyric_lang: str = Form(default="Mandarin",
        description='"Mandarin" / "Cantonese" / "English"'),
    target_lyric_lang: str = Form(default="Mandarin"),
    prompt_vocal_sep: bool = Form(default=False, description="参考音频声伴分离"),
    target_vocal_sep: bool = Form(default=True, description="目标音频声伴分离"),
    # ---- 可选 metadata（精确控制歌词+旋律对齐）----
    prompt_metadata: Optional[UploadFile] = File(None, description="Prompt metadata JSON"),
    target_metadata: Optional[UploadFile] = File(None, description="Target metadata JSON"),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """歌声合成 (SVS) — 输入两段音频，模型自动转写歌词和提取旋律"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    await _singer_preflight()

    prompt_path, prompt_url = await _save_upload(prompt_audio, ".wav")
    target_path, target_url = await _save_upload(target_audio, ".wav")
    prompt_meta_path = (await _save_upload(prompt_metadata, ".json"))[0] if prompt_metadata else None
    target_meta_path = (await _save_upload(target_metadata, ".json"))[0] if target_metadata else None

    params = json.dumps({
        "control": control, "auto_shift": auto_shift, "pitch_shift": pitch_shift,
        "seed": seed, "prompt_lyric_lang": prompt_lyric_lang,
        "target_lyric_lang": target_lyric_lang,
        "prompt_vocal_sep": prompt_vocal_sep, "target_vocal_sep": target_vocal_sep,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.singing_svs,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_audio_url=prompt_url,
        source_audio_url=target_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_svs_task, task.id,
        prompt_path, target_path, control, auto_shift, pitch_shift, seed,
        prompt_lyric_lang, target_lyric_lang, prompt_vocal_sep, target_vocal_sep,
        prompt_meta_path, target_meta_path,
    )
    return SVSResponse(task_id=task.id, status=task.status.value)


@router.post("/svc", response_model=SVCResponse)
async def singing_voice_conversion(
    background_tasks: BackgroundTasks,
    # ---- 两段音频 ----
    prompt_audio: UploadFile = File(..., description="目标音色参考音频"),
    target_audio: UploadFile = File(..., description="待转换的源歌曲音频"),
    # ---- 高级参数 ----
    prompt_vocal_sep: bool = Form(default=False),
    target_vocal_sep: bool = Form(default=True, description="源音频声伴分离"),
    auto_shift: bool = Form(default=True, description="自动音高偏移"),
    auto_mix_acc: bool = Form(default=True, description="自动混合伴奏到输出"),
    pitch_shift: int = Form(default=0, ge=-36, le=36),
    n_step: int = Form(default=32, ge=1, le=200, description="扩散步数"),
    cfg: float = Form(default=1.0, ge=0.0, le=10.0, description="CFG scale"),
    use_fp16: bool = Form(default=True),
    seed: int = Form(default=42),
    # ---- 鉴权 ----
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """歌声转换 (SVC) — 音频到音频的音色转换"""
    if not settings.SOUL_ENABLED:
        raise HTTPException(status_code=503, detail="Soul AI features disabled")

    prompt_path, prompt_url = await _save_upload(prompt_audio, ".wav")
    target_path, target_url = await _save_upload(target_audio, ".wav")

    params = json.dumps({
        "prompt_vocal_sep": prompt_vocal_sep, "target_vocal_sep": target_vocal_sep,
        "auto_shift": auto_shift, "auto_mix_acc": auto_mix_acc,
        "pitch_shift": pitch_shift, "n_step": n_step, "cfg": cfg,
        "use_fp16": use_fp16, "seed": seed,
    }, ensure_ascii=False)

    task = SoulTask(
        user_id=current_user.id,
        task_type=SoulTaskType.singing_svc,
        status=SoulTaskStatus.pending,
        input_params=params,
        ref_audio_url=prompt_url,
        source_audio_url=target_url,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(
        process_svc_task, task.id,
        prompt_path, target_path,
        prompt_vocal_sep, target_vocal_sep, auto_shift, auto_mix_acc,
        pitch_shift, n_step, cfg, use_fp16, seed,
    )
    return SVCResponse(task_id=task.id, status=task.status.value)


@router.get("/tasks", response_model=List[SoulTaskDetail])
async def get_singing_tasks(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SoulTask)
        .where(
            SoulTask.task_type.in_([SoulTaskType.singing_svs, SoulTaskType.singing_svc]),
        )
        .order_by(desc(SoulTask.created_at))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/tasks/{task_id}", response_model=SoulTaskDetail)
async def get_singing_task(
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
async def singing_health():
    """检查 Singer Space 是否在线"""
    online = await singer_client.health_check()
    return {"space": settings.SOUL_SINGER_SPACE, "online": online}
