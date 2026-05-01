"""Agent 运行记录查询 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db.database import get_db

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


def _row(r) -> dict:
    return dict(r)


@router.get("")
async def list_runs(execution_id: str = "", session_id: str = "", limit: int = 50):
    db = await get_db()
    conds, params = [], []
    if execution_id:
        conds.append("execution_id = ?"); params.append(execution_id)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    cur = await db.execute(
        f"SELECT * FROM agent_runs {where} ORDER BY created_at DESC LIMIT ?",
        [*params, limit],
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}


@router.get("/{run_id}")
async def get_run(run_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    result = _row(row)
    # 附带消息列表
    msg_cur = await db.execute(
        "SELECT * FROM agent_messages WHERE run_id = ? ORDER BY created_at", (run_id,)
    )
    result["messages"] = [_row(m) for m in await msg_cur.fetchall()]
    return result


@router.get("/by-execution/{execution_id}")
async def get_runs_by_execution(execution_id: str):
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM agent_runs WHERE execution_id = ? ORDER BY agent_index",
        (execution_id,),
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}
