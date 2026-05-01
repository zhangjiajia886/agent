from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KBCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "file"
    config: dict = {}


class KBUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    status: str | None = None


@router.get("")
async def list_knowledge_bases(search: str = ""):
    db = await get_db()
    query = "SELECT * FROM knowledge_bases WHERE 1=1"
    params: list = []
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY updated_at DESC"
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    return {"items": [_row(r) for r in items]}


@router.post("")
async def create_knowledge_base(body: KBCreate):
    db = await get_db()
    kid = f"kb_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO knowledge_bases (id, name, description, type, config, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (kid, body.name, body.description, body.type, json.dumps(body.config), now, now),
    )
    await db.commit()
    return {"id": kid, "name": body.name}


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Knowledge base not found")
    return _row(item)


@router.put("/{kb_id}")
async def update_knowledge_base(kb_id: str, body: KBUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.config is not None:
        fields.append("config = ?"); params.append(json.dumps(body.config))
    if body.status is not None:
        fields.append("status = ?"); params.append(body.status)
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(kb_id)
        await db.execute(f"UPDATE knowledge_bases SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    db = await get_db()
    await db.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
    await db.commit()
    return {"ok": True}


def _row(r) -> dict:
    d = dict(r)
    if "config" in d and isinstance(d["config"], str):
        try:
            d["config"] = json.loads(d["config"])
        except Exception:
            pass
    return d
