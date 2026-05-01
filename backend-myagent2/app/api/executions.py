from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from ..db.database import get_db
from ..core.cancellation import CancellationToken
from ..engine.checkpoint import CheckpointManager
from .workflows import _running_executions, _row_to_dict

router = APIRouter(prefix="/api/executions", tags=["executions"])


@router.get("")
async def list_executions(
    workflow_id: str = "",
    status: str = "",
    skip: int = 0,
    limit: int = 50,
):
    db = await get_db()
    query = "SELECT * FROM executions WHERE 1=1"
    params: list = []
    if workflow_id:
        query += " AND workflow_id = ?"
        params.append(workflow_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    rows = await db.execute(query, params)
    items = await rows.fetchall()

    count_q = "SELECT COUNT(*) FROM executions WHERE 1=1"
    count_params: list = []
    if workflow_id:
        count_q += " AND workflow_id = ?"
        count_params.append(workflow_id)
    if status:
        count_q += " AND status = ?"
        count_params.append(status)
    count_row = await db.execute(count_q, count_params)
    total = (await count_row.fetchone())[0]

    return {"items": [_row_to_dict(r) for r in items], "total": total}


@router.get("/{execution_id}")
async def get_execution(execution_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Execution not found")
    return _row_to_dict(item)


@router.get("/{execution_id}/traces")
async def get_execution_traces(execution_id: str):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM trace_spans WHERE execution_id = ? ORDER BY start_time",
        (execution_id,),
    )
    items = await rows.fetchall()
    return {"items": [dict(r) for r in items]}


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    token = _running_executions.get(execution_id)
    if not token:
        raise HTTPException(404, "Execution not running or not found")
    token.cancel()
    db = await get_db()
    await db.execute(
        "UPDATE executions SET status = 'cancelled' WHERE id = ? AND status = 'running'",
        (execution_id,),
    )
    await db.commit()
    return {"ok": True, "status": "cancelled"}


@router.get("/{execution_id}/checkpoint")
async def get_checkpoint(execution_id: str):
    """查询断点状态及已完成节点进度。"""
    ckpt_mgr = CheckpointManager(execution_id)
    info = await ckpt_mgr.get_info()
    if not info:
        return {"has_checkpoint": False, "completed_nodes": [], "completed_count": 0}
    # 获取工作流总节点数
    db = await get_db()
    row = await db.execute(
        "SELECT node_statuses FROM executions WHERE id = ?", (execution_id,)
    )
    exec_row = await row.fetchone()
    total_nodes = 0
    if exec_row:
        ns = (dict(exec_row) if not isinstance(exec_row, dict) else exec_row).get("node_statuses")
        if ns:
            try:
                total_nodes = len(json.loads(ns))
            except Exception:
                pass
    info["total_nodes"] = total_nodes
    info["progress_pct"] = round(info["completed_count"] / total_nodes * 100) if total_nodes else 0
    return info


@router.delete("/{execution_id}/checkpoint")
async def delete_checkpoint(execution_id: str):
    """清除断点（执行成功后清理）。"""
    ckpt_mgr = CheckpointManager(execution_id)
    await ckpt_mgr.delete()
    return {"ok": True}


@router.post("/{execution_id}/resume")
async def resume_execution(execution_id: str, request: Request):
    """从断点继续执行工作流。若无断点则从头执行。"""
    db = await get_db()
    row = await db.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Execution not found")
    exec_data = _row_to_dict(item)

    if exec_data.get("status") == "running":
        raise HTTPException(400, "Execution is already running")

    # 获取工作流定义
    wf_row = await db.execute(
        "SELECT * FROM workflows WHERE id = ?", (exec_data["workflow_id"],)
    )
    wf_item = await wf_row.fetchone()
    if not wf_item:
        raise HTTPException(404, "Workflow not found")
    wf = _row_to_dict(wf_item)
    definition = wf["definition"]
    inputs = json.loads(exec_data.get("inputs") or "{}")

    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE executions SET status='running', started_at=?, finished_at=NULL, error=NULL WHERE id=?",
        (now, execution_id),
    )
    await db.commit()

    cancel_token = CancellationToken()
    _running_executions[execution_id] = cancel_token

    engine = request.app.state.engine
    asyncio.create_task(
        _resume_execution_task(db, execution_id, engine, definition, inputs, cancel_token)
    )
    return {"execution_id": execution_id, "status": "running", "resumed": True}


async def _resume_execution_task(db, exec_id, engine, definition, inputs, cancel_token):
    from .workflows import _run_execution  # 复用已有的完成逻辑
    try:
        result = await engine.execute(exec_id, definition, inputs, cancel_token, resume=True)
        status = result.get("status", "done")
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE executions SET status=?, outputs=?, node_statuses=?, finished_at=? WHERE id=?",
            (
                status,
                json.dumps(result.get("outputs", {})),
                json.dumps(result.get("node_statuses", {})),
                now,
                exec_id,
            ),
        )
        await db.commit()
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE executions SET status='error', error=?, finished_at=? WHERE id=?",
            (str(e), now, exec_id),
        )
        await db.commit()
    finally:
        _running_executions.pop(exec_id, None)


@router.post("/{execution_id}/kill")
async def kill_execution(execution_id: str):
    token = _running_executions.get(execution_id)
    if token:
        token.cancel()
    db = await get_db()
    await db.execute(
        "UPDATE executions SET status = 'killed' WHERE id = ? AND status IN ('running', 'pending')",
        (execution_id,),
    )
    await db.commit()
    _running_executions.pop(execution_id, None)
    return {"ok": True, "status": "killed"}
