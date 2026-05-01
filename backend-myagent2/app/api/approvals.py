"""HITL Approval 审批历史查询与处理接口。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.database import get_db
from ..core.auth import get_current_user_optional

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _row(r) -> dict:
    return dict(r)


class ApprovalDecision(BaseModel):
    decision: str  # approved | rejected
    note: str = ""


@router.get("")
async def list_approvals(
    session_id: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """列出审批请求，支持按会话和状态过滤。"""
    db = await get_db()
    conds = []
    params: list = []

    if session_id:
        conds.append("session_id = ?")
        params.append(session_id)
    if status:
        conds.append("status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(conds)}" if conds else ""

    count_cur = await db.execute(
        f"SELECT COUNT(*) FROM approval_requests {where}", params
    )
    count_row = await count_cur.fetchone()
    total = (count_row[0] if isinstance(count_row, (list, tuple)) else count_row["COUNT(*)"]) or 0

    cur = await db.execute(
        f"SELECT * FROM approval_requests {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows], "total": total}


@router.get("/{approval_id}")
async def get_approval(approval_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (approval_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Approval not found")
    return _row(row)


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    current_user: dict | None = Depends(get_current_user_optional),
):
    """人工审批：批准或拒绝工具调用请求。"""
    db = await get_db()
    cur = await db.execute("SELECT * FROM approval_requests WHERE id = ?", (approval_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Approval not found")

    item = _row(row)
    if item.get("status") != "pending":
        raise HTTPException(400, f"Approval already decided: {item.get('status')}")

    if body.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    now = datetime.now(timezone.utc).isoformat()
    decided_by = current_user["sub"] if current_user else "anonymous"

    await db.execute(
        """UPDATE approval_requests
           SET status=?, decided_by=?, decision_note=?, decided_at=?
           WHERE id=?""",
        (body.decision, decided_by, body.note, now, approval_id),
    )
    await db.commit()

    # 通知 agent loop（通过 _confirm_actions 事件）
    try:
        from ..agent.loop import _confirm_actions
        if approval_id in _confirm_actions:
            _confirm_actions[approval_id].set()
    except Exception:
        pass

    return {"ok": True, "status": body.decision}


@router.get("/pending/count")
async def pending_count():
    """返回待审批数量，用于 badge 提示。"""
    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM approval_requests WHERE status = 'pending'"
    )
    row = await cur.fetchone()
    count = (row[0] if isinstance(row, (list, tuple)) else row["COUNT(*)"]) or 0
    return {"count": count}
