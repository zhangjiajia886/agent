from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/memories", tags=["memories"])


# ── Pydantic Models ──────────────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    title: str
    content: str
    type: str = "fact"
    tags: str = ""
    scope: str = "global"
    scope_id: str = ""
    created_by: str = ""
    source_session_id: str = ""
    source_message_id: str = ""


class MemoryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    type: str | None = None
    tags: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(r) -> dict:
    return dict(r)


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_memories(
    scope: str = Query(default="global"),
    scope_id: str = Query(default=""),
    type: str = Query(default=""),
    tags: str = Query(default=""),
    created_by: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    db = await get_db()
    conds = ["is_active = 1"]
    filter_params: list = []

    if scope:
        conds.append("scope = ?")
        filter_params.append(scope)
    if scope_id:
        conds.append("scope_id = ?")
        filter_params.append(scope_id)
    if type:
        conds.append("type = ?")
        filter_params.append(type)
    if tags:
        conds.append("tags LIKE ?")
        filter_params.append(f"%{tags}%")
    if created_by:
        conds.append("created_by = ?")
        filter_params.append(created_by)

    where = " AND ".join(conds)

    cur = await db.execute(
        f"SELECT * FROM memories WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        filter_params + [limit, offset],
    )
    rows = await cur.fetchall()

    count_cur = await db.execute(
        f"SELECT COUNT(*) AS cnt FROM memories WHERE {where}",
        filter_params,
    )
    count_row = await count_cur.fetchone()
    total = (count_row["cnt"] if isinstance(count_row, dict) else count_row[0]) if count_row else 0

    return {"items": [_row(r) for r in rows], "total": total}


@router.post("", status_code=201)
async def create_memory(body: MemoryCreate):
    db = await get_db()
    mid = f"mem_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        """INSERT INTO memories
           (id, title, content, type, tags, scope, scope_id,
            created_by, source_session_id, source_message_id,
            version, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?,  ?, ?, ?,  1, 1, ?, ?)""",
        (
            mid, body.title, body.content, body.type, body.tags,
            body.scope, body.scope_id or None,
            body.created_by or None,
            body.source_session_id or None,
            body.source_message_id or None,
            now, now,
        ),
    )
    await db.commit()
    return {"id": mid, "created_at": now}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, include_history: bool = False):
    db = await get_db()
    cur = await db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Memory not found")

    result = _row(row)

    if include_history:
        history = []
        prev_id = result.get("prev_id")
        while prev_id:
            hcur = await db.execute("SELECT * FROM memories WHERE id = ?", (prev_id,))
            hrow = await hcur.fetchone()
            if not hrow:
                break
            hdict = _row(hrow)
            history.append(hdict)
            prev_id = hdict.get("prev_id")
        result["history"] = history

    return result


@router.put("/{memory_id}")
async def update_memory(memory_id: str, body: MemoryUpdate):
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM memories WHERE id = ? AND is_active = 1", (memory_id,)
    )
    old = await cur.fetchone()
    if not old:
        raise HTTPException(404, "Memory not found")

    old_dict = _row(old)
    now = datetime.now(timezone.utc).isoformat()
    new_id = f"mem_{uuid.uuid4().hex[:12]}"

    # 旧版本失效
    await db.execute(
        "UPDATE memories SET is_active = 0, updated_at = ? WHERE id = ?",
        (now, memory_id),
    )

    # 创建新版本（继承旧值，覆盖变化字段）
    await db.execute(
        """INSERT INTO memories
           (id, title, content, type, tags, scope, scope_id,
            created_by, source_session_id, source_message_id,
            version, prev_id, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?,  ?, ?, ?,  ?, ?, 1, ?, ?)""",
        (
            new_id,
            body.title if body.title is not None else old_dict["title"],
            body.content if body.content is not None else old_dict["content"],
            body.type if body.type is not None else old_dict.get("type"),
            body.tags if body.tags is not None else old_dict.get("tags"),
            old_dict.get("scope"),
            old_dict.get("scope_id"),
            old_dict.get("created_by"),
            old_dict.get("source_session_id"),
            old_dict.get("source_message_id"),
            (old_dict.get("version") or 1) + 1,
            memory_id,
            now, now,
        ),
    )
    await db.commit()
    return {"id": new_id, "prev_id": memory_id, "updated_at": now}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    result = await db.execute(
        "UPDATE memories SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1",
        (now, memory_id),
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Memory not found or already deleted")
    return {"ok": True}
