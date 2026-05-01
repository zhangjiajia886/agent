from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Pydantic Models ──────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    parent_id: str = ""
    session_id: str = ""
    session_type: str = "chat"
    execution_id: str = ""
    tool_hint: str = ""
    due_at: str = ""


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    result: Optional[str] = None
    progress: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(r) -> dict:
    return dict(r)


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_tasks(
    session_id: str = Query(default=""),
    session_type: str = Query(default=""),
    status: str = Query(default=""),
    execution_id: str = Query(default=""),
    root_only: bool = Query(default=False),
    limit: int = Query(default=100, le=500),
):
    db = await get_db()
    conds = ["1=1"]
    params: list = []

    if session_id:
        conds.append("session_id = ?")
        params.append(session_id)
    if session_type:
        conds.append("session_type = ?")
        params.append(session_type)
    if status:
        conds.append("status = ?")
        params.append(status)
    if execution_id:
        conds.append("execution_id = ?")
        params.append(execution_id)
    if root_only:
        conds.append("parent_id IS NULL")

    params.append(limit)
    where = " AND ".join(conds)

    cur = await db.execute(
        f"SELECT * FROM tasks WHERE {where} ORDER BY depth, order_index, created_at LIMIT ?",
        params,
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}


@router.post("", status_code=201)
async def create_task(body: TaskCreate):
    db = await get_db()
    tid = f"task_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    parent_id = body.parent_id or None
    root_id = tid
    depth = 0
    order_index = 0

    if parent_id:
        cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (parent_id,))
        parent = await cur.fetchone()
        if not parent:
            raise HTTPException(404, f"Parent task {parent_id} not found")
        p = _row(parent)
        root_id = p.get("root_id") or parent_id
        depth = (p.get("depth") or 0) + 1
        # 当前最大 order_index + 1
        ocur = await db.execute(
            "SELECT COALESCE(MAX(order_index), -1) AS max_idx FROM tasks WHERE parent_id = ?",
            (parent_id,),
        )
        orow = await ocur.fetchone()
        order_index = ((orow["max_idx"] if isinstance(orow, dict) else orow[0]) or -1) + 1

    await db.execute(
        """INSERT INTO tasks
           (id, parent_id, root_id, depth, order_index, title, description,
            status, priority, session_id, session_type, execution_id, tool_hint,
            due_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?,  'pending', ?, ?, ?, ?, ?,  ?, ?, ?)""",
        (
            tid, parent_id, root_id, depth, order_index,
            body.title, body.description or None,
            body.priority,
            body.session_id or None, body.session_type or "chat",
            body.execution_id or None, body.tool_hint or None,
            body.due_at or None,
            now, now,
        ),
    )
    await db.commit()
    return {"id": tid, "root_id": root_id, "depth": depth, "created_at": now}


@router.get("/{task_id}")
async def get_task(task_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    return _row(row)


@router.get("/{task_id}/tree")
async def get_task_tree(task_id: str):
    """返回以 task_id 为根的完整任务树。"""
    db = await get_db()
    cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    root = await cur.fetchone()
    if not root:
        raise HTTPException(404, "Task not found")
    root_dict = _row(root)

    # 取同 root_id 的所有子孙
    dcur = await db.execute(
        "SELECT * FROM tasks WHERE root_id = ? ORDER BY depth, order_index",
        (root_dict.get("root_id") or task_id,),
    )
    all_rows = [_row(r) for r in await dcur.fetchall()]

    # 组装树形结构
    by_id = {r["id"]: {**r, "children": []} for r in all_rows}
    tree_root = None
    for item in by_id.values():
        pid = item.get("parent_id")
        if pid and pid in by_id:
            by_id[pid]["children"].append(item)
        elif item["id"] == task_id:
            tree_root = item

    return tree_root or root_dict


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    db = await get_db()
    cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")

    now = datetime.now(timezone.utc).isoformat()
    fields, params = ["updated_at = ?"], [now]

    if body.title is not None:
        fields.append("title = ?"); params.append(body.title)
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.status is not None:
        fields.append("status = ?"); params.append(body.status)
        if body.status in ("completed", "cancelled"):
            fields.append("finished_at = ?"); params.append(now)
        elif body.status == "in_progress":
            fields.append("started_at = ?"); params.append(now)
    if body.priority is not None:
        fields.append("priority = ?"); params.append(body.priority)
    if body.result is not None:
        fields.append("result = ?"); params.append(body.result)

    params.append(task_id)
    await db.execute(
        f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params
    )
    await db.commit()

    # 若所有子任务完成，自动推进父任务状态
    t = _row(row)
    parent_id = t.get("parent_id")
    if body.status == "completed" and parent_id:
        scur = await db.execute(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE parent_id = ? AND status != 'completed'",
            (parent_id,),
        )
        srow = await scur.fetchone()
        remaining = (srow["cnt"] if isinstance(srow, dict) else srow[0]) if srow else 1
        if remaining == 0:
            await db.execute(
                "UPDATE tasks SET status='completed', finished_at=?, updated_at=? WHERE id=?",
                (now, now, parent_id),
            )
            await db.commit()

    return {"ok": True, "updated_at": now}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    db = await get_db()
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.commit()
    return {"ok": True}
