from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.db.session import get_db
from app.models.user import User
from app.models.voice_model import VoiceModel
from app.schemas.voice_model import VoiceModelCreate, VoiceModelUpdate, VoiceModelResponse, VoiceModelList
from app.api.v1.auth import get_current_user
from app.core.fish_speech import fish_client
from loguru import logger

router = APIRouter()


@router.post("/", response_model=VoiceModelResponse)
async def create_voice_model(
    title: str = Form(...),
    description: str = Form(""),
    language: str = Form("zh"),
    visibility: str = Form("private"),
    audio_files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not audio_files:
        raise HTTPException(status_code=400, detail="At least one audio file is required")
    
    try:
        audio_data_list = []
        for audio_file in audio_files:
            content = await audio_file.read()
            audio_data_list.append({
                "content": content,
                "filename": audio_file.filename or "sample.wav",
                "content_type": audio_file.content_type or "audio/wav",
            })
        
        fish_result = await fish_client.create_voice_model(
            title=title,
            audio_files=audio_data_list,
            description=description,
            visibility=visibility,
        )
        
        voice_model = VoiceModel(
            user_id=current_user.id,
            fish_model_id=fish_result["_id"],
            title=title,
            description=description,
            language=language,
            visibility=visibility,
        )
        
        db.add(voice_model)
        await db.commit()
        await db.refresh(voice_model)
        
        return voice_model
        
    except Exception as e:
        logger.error(f"Create voice model failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=VoiceModelList)
async def get_voice_models(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(VoiceModel)
        .where(VoiceModel.is_deleted == False)
        .order_by(desc(VoiceModel.created_at))
        .offset(skip)
        .limit(limit)
    )
    models = result.scalars().all()
    
    count_result = await db.execute(
        select(VoiceModel)
        .where(VoiceModel.is_deleted == False)
    )
    total = len(count_result.scalars().all())
    
    return VoiceModelList(total=total, items=models)


@router.get("/{model_id}", response_model=VoiceModelResponse)
async def get_voice_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == model_id,
            VoiceModel.is_deleted == False
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Voice model not found")
    
    return model


@router.patch("/{model_id}", response_model=VoiceModelResponse)
async def update_voice_model(
    model_id: int,
    model_update: VoiceModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == model_id,
            VoiceModel.user_id == current_user.id,
            VoiceModel.is_deleted == False
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Voice model not found")
    
    if model_update.title is not None:
        model.title = model_update.title
    if model_update.description is not None:
        model.description = model_update.description
    if model_update.visibility is not None:
        model.visibility = model_update.visibility
    
    await db.commit()
    await db.refresh(model)
    
    return model


@router.delete("/{model_id}")
async def delete_voice_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(VoiceModel).where(
            VoiceModel.id == model_id,
            VoiceModel.user_id == current_user.id,
            VoiceModel.is_deleted == False
        )
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Voice model not found")
    
    model.is_deleted = True
    await db.commit()
    
    try:
        await fish_client.delete_voice_model(model.fish_model_id)
    except Exception as e:
        logger.warning(f"Failed to delete Fish Speech model: {e}")
    
    return {"message": "Voice model deleted successfully"}


@router.get("/official/search")
async def search_official_voices(
    title: str = Query("", description="搜索关键词"),
    tag: str = Query("", description="标签过滤"),
    page_size: int = Query(20, le=50),
    page_number: int = Query(1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索 Fish Audio 公开音色库"""
    try:
        result = await fish_client.search_public_models(
            title=title, tag=tag,
            page_size=page_size, page_number=page_number,
        )
        items = result.get("items", [])
        existing = await db.execute(
            select(VoiceModel.fish_model_id)
            .where(VoiceModel.is_deleted == False)
        )
        imported_ids = {row[0] for row in existing.all()}
        for item in items:
            item["already_imported"] = item.get("_id") in imported_ids
        return {"total": result.get("total", len(items)), "items": items}
    except Exception as e:
        logger.error(f"Search official voices failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-official")
async def import_official_voices(
    fish_model_ids: List[str],
    language: Optional[str] = "zh",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """将选中的 Fish Audio 公开音色导入到本地音色库"""
    imported = []
    skipped = []
    for fish_id in fish_model_ids:
        existing = await db.execute(
            select(VoiceModel).where(
                VoiceModel.fish_model_id == fish_id,
                VoiceModel.user_id == current_user.id,
            )
        )
        if existing.scalar_one_or_none():
            skipped.append(fish_id)
            continue
        try:
            model_info = await fish_client.get_voice_model_detail(fish_id)
            vm = VoiceModel(
                user_id=current_user.id,
                fish_model_id=fish_id,
                title=model_info.get("title", fish_id),
                description=model_info.get("description", ""),
                language=language or "zh",
                visibility="public",
            )
            db.add(vm)
            imported.append(fish_id)
        except Exception as e:
            logger.warning(f"Import {fish_id} failed: {e}")
            skipped.append(fish_id)
    await db.commit()
    return {"imported": len(imported), "skipped": len(skipped)}
