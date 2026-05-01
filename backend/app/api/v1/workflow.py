"""
工作流 DAG 引擎 API — CRUD + 执行 + 断点恢复
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.session import get_db
from app.models.workflow import (
    WorkflowDefinition, WorkflowExecution, ExecutionStatus, ExecutionCheckpoint,
)
from app.models.agent_config import ModelConfig
from app.schemas.workflow import (
    WorkflowDefinitionSchema, WorkflowDefinitionCreate, WorkflowDefinitionUpdate,
    WorkflowExecutionSchema, WorkflowExecuteRequest, CheckpointInfoSchema,
)
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.core.comic_engine.executor import WorkflowEngine
from app.core.comic_engine.checkpoint import CheckpointManager

router = APIRouter()


# ═══════════════════ 工作流定义 CRUD ═══════════════════

@router.get("/dag", response_model=List[WorkflowDefinitionSchema])
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowDefinition).order_by(WorkflowDefinition.created_at.desc())
    )
    return result.scalars().all()


@router.post("/dag", response_model=WorkflowDefinitionSchema)
async def create_workflow(
    body: WorkflowDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wf = WorkflowDefinition(
        id=f"wf_{uuid.uuid4().hex[:12]}",
        name=body.name,
        description=body.description or "",
        definition=body.definition,
        is_enabled=body.is_enabled,
    )
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return wf


@router.get("/dag/{wf_id}", response_model=WorkflowDefinitionSchema)
async def get_workflow(wf_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "工作流不存在")
    return wf


@router.put("/dag/{wf_id}", response_model=WorkflowDefinitionSchema)
async def update_workflow(
    wf_id: str,
    body: WorkflowDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "工作流不存在")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(wf, field, val)
    await db.flush()
    await db.refresh(wf)
    return wf


@router.delete("/dag/{wf_id}")
async def delete_workflow(
    wf_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "工作流不存在")
    await db.delete(wf)
    return {"ok": True}


# ═══════════════════ 工作流执行 ═══════════════════

@router.post("/dag/{wf_id}/execute", response_model=WorkflowExecutionSchema)
async def execute_workflow(
    wf_id: str,
    body: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """同步执行工作流（适合短工作流）"""
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "工作流不存在")

    exec_id = f"exec_{uuid.uuid4().hex[:12]}"

    # 创建执行记录
    execution = WorkflowExecution(
        id=exec_id,
        workflow_id=wf_id,
        user_id=str(user.id),
        status=ExecutionStatus.running,
        inputs=body.inputs,
    )
    db.add(execution)
    await db.flush()

    # 获取默认 LLM 配置
    llm_config = await _get_default_llm_config(db)

    # 执行
    engine = WorkflowEngine()
    engine_result = await engine.execute(
        execution_id=exec_id,
        workflow=wf.definition,
        inputs=body.inputs,
        resume=body.resume,
        llm_config=llm_config,
    )

    # 更新执行记录
    execution.status = ExecutionStatus(engine_result.get("status", "error"))
    execution.outputs = engine_result.get("outputs")
    execution.node_statuses = engine_result.get("node_statuses")
    execution.finished_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(execution)

    return execution


@router.get("/dag/{wf_id}/executions", response_model=List[WorkflowExecutionSchema])
async def list_executions(wf_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == wf_id)
        .order_by(WorkflowExecution.started_at.desc())
        .limit(20)
    )
    return result.scalars().all()


@router.get("/executions/{exec_id}", response_model=WorkflowExecutionSchema)
async def get_execution(exec_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
    )
    ex = result.scalar_one_or_none()
    if not ex:
        raise HTTPException(404, "执行记录不存在")
    return ex


@router.get("/executions/{exec_id}/checkpoint", response_model=CheckpointInfoSchema)
async def get_checkpoint_info(exec_id: str):
    ckpt_mgr = CheckpointManager(exec_id)
    info = await ckpt_mgr.get_info()
    if not info:
        return CheckpointInfoSchema(has_checkpoint=False)
    return CheckpointInfoSchema(**info)


@router.post("/executions/{exec_id}/resume", response_model=WorkflowExecutionSchema)
async def resume_execution(
    exec_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """从断点恢复执行"""
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(404, "执行记录不存在")

    # 加载工作流定义
    wf_result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == execution.workflow_id)
    )
    wf = wf_result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "关联工作流不存在")

    execution.status = ExecutionStatus.running
    await db.flush()

    llm_config = await _get_default_llm_config(db)

    engine = WorkflowEngine()
    engine_result = await engine.execute(
        execution_id=exec_id,
        workflow=wf.definition,
        inputs=execution.inputs or {},
        resume=True,
        llm_config=llm_config,
    )

    execution.status = ExecutionStatus(engine_result.get("status", "error"))
    execution.outputs = engine_result.get("outputs")
    execution.node_statuses = engine_result.get("node_statuses")
    execution.finished_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(execution)

    return execution


# ═══════════════════ WebSocket 实时执行 ═══════════════════

@router.websocket("/dag/{wf_id}/ws")
async def ws_execute_workflow(websocket: WebSocket, wf_id: str):
    """WebSocket 实时执行工作流，推送节点状态事件"""
    await websocket.accept()

    try:
        # 接收执行参数
        data = await websocket.receive_json()
        inputs = data.get("inputs", {})
        resume = data.get("resume", False)

        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WorkflowDefinition).where(WorkflowDefinition.id == wf_id)
            )
            wf = result.scalar_one_or_none()
            if not wf:
                await websocket.send_json({"type": "error", "content": "工作流不存在"})
                await websocket.close()
                return

            exec_id = data.get("execution_id") or f"exec_{uuid.uuid4().hex[:12]}"

            # 创建或恢复执行记录
            if not resume:
                execution = WorkflowExecution(
                    id=exec_id,
                    workflow_id=wf_id,
                    status=ExecutionStatus.running,
                    inputs=inputs,
                )
                db.add(execution)
                await db.commit()

            llm_config = await _get_default_llm_config(db)

        # 事件回调：推送到 WebSocket
        async def on_event(event: dict):
            try:
                await websocket.send_json(event)
            except Exception:
                pass

        engine = WorkflowEngine(on_event=on_event)
        engine_result = await engine.execute(
            execution_id=exec_id,
            workflow=wf.definition,
            inputs=inputs,
            resume=resume,
            llm_config=llm_config,
        )

        # 更新执行记录
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
            execution = result.scalar_one_or_none()
            if execution:
                execution.status = ExecutionStatus(engine_result.get("status", "error"))
                execution.outputs = engine_result.get("outputs")
                execution.node_statuses = engine_result.get("node_statuses")
                execution.finished_at = datetime.now(timezone.utc)
                await db.commit()

        await websocket.send_json({
            "type": "done",
            "execution_id": exec_id,
            "status": engine_result.get("status", "error"),
        })

    except WebSocketDisconnect:
        logger.info(f"[WF WS] client disconnected")
    except Exception as e:
        logger.error(f"[WF WS] error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ═══════════════════ 辅助 ═══════════════════

async def _get_default_llm_config(db: AsyncSession) -> dict:
    """获取默认 agent_brain 模型配置"""
    result = await db.execute(
        select(ModelConfig).where(
            ModelConfig.category == "agent_brain",
            ModelConfig.is_default == True,
            ModelConfig.is_enabled == True,
        ).limit(1)
    )
    model = result.scalar_one_or_none()
    if not model:
        return {}
    return {
        "base_url": model.base_url,
        "api_key": model.api_key or "",
        "model": model.model_id,
    }
