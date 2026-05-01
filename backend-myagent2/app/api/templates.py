from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db
from .workflows import _row_to_dict

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    definition: dict = {}
    tags: list[str] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    definition: dict | None = None
    tags: list[str] | None = None


@router.get("")
async def list_templates(category: str = "", search: str = ""):
    db = await get_db()
    query = "SELECT * FROM templates WHERE 1=1"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY updated_at DESC"
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    return {"items": [_row_to_dict(r) for r in items]}


@router.post("")
async def create_template(body: TemplateCreate):
    db = await get_db()
    tid = f"tpl_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO templates (id, name, description, category, definition, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (tid, body.name, body.description, body.category, json.dumps(body.definition), json.dumps(body.tags), now, now),
    )
    await db.commit()
    return {"id": tid, "name": body.name}


@router.get("/{template_id}")
async def get_template(template_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Template not found")
    return _row_to_dict(item)


@router.put("/{template_id}")
async def update_template(template_id: str, body: TemplateUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.category is not None:
        fields.append("category = ?"); params.append(body.category)
    if body.definition is not None:
        fields.append("definition = ?"); params.append(json.dumps(body.definition))
    if body.tags is not None:
        fields.append("tags = ?"); params.append(json.dumps(body.tags))
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(template_id)
        await db.execute(f"UPDATE templates SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    db = await get_db()
    await db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{template_id}/import")
async def import_from_template(template_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Template not found")
    d = _row_to_dict(item)
    wf_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO workflows (id, name, description, definition, status, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (wf_id, d["name"], d["description"], json.dumps(d["definition"]), "draft", json.dumps(d.get("tags", [])), now, now),
    )
    await db.commit()
    return {"workflow_id": wf_id}
