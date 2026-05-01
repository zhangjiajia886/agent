from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "system"
    content: str = ""
    variables: list[str] = []
    tags: list[str] = []


class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    content: str | None = None
    variables: list[str] | None = None
    tags: list[str] | None = None


@router.get("")
async def list_prompts(type: str = "", search: str = ""):
    db = await get_db()
    query = "SELECT * FROM prompts WHERE 1=1"
    params: list = []
    if type:
        query += " AND type = ?"
        params.append(type)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY updated_at DESC"
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    return {"items": [_row(r) for r in items]}


@router.post("")
async def create_prompt(body: PromptCreate):
    db = await get_db()
    pid = f"prompt_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO prompts (id, name, description, type, content, variables, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, body.name, body.description, body.type, body.content, json.dumps(body.variables), json.dumps(body.tags), now, now),
    )
    await db.commit()
    return {"id": pid, "name": body.name}


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Prompt not found")
    return _row(item)


@router.put("/{prompt_id}")
async def update_prompt(prompt_id: str, body: PromptUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.type is not None:
        fields.append("type = ?"); params.append(body.type)
    if body.content is not None:
        fields.append("content = ?"); params.append(body.content)
    if body.variables is not None:
        fields.append("variables = ?"); params.append(json.dumps(body.variables))
    if body.tags is not None:
        fields.append("tags = ?"); params.append(json.dumps(body.tags))
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(prompt_id)
        await db.execute(f"UPDATE prompts SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{prompt_id}")
async def delete_prompt(prompt_id: str):
    db = await get_db()
    await db.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
    await db.commit()
    return {"ok": True}


def _row(r) -> dict:
    d = dict(r)
    for k in ("variables", "tags"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    d["is_builtin"] = bool(d.get("is_builtin", 0))
    return d
