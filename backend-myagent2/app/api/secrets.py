from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SecretCreate(BaseModel):
    name: str
    value: str
    description: str = ""


class SecretUpdate(BaseModel):
    value: str | None = None
    description: str | None = None


@router.get("")
async def list_secrets():
    db = await get_db()
    rows = await db.execute(
        "SELECT id, name, description, created_at, updated_at FROM secrets ORDER BY name"
    )
    items = await rows.fetchall()
    return {"items": [dict(r) for r in items]}


@router.post("")
async def create_secret(body: SecretCreate):
    db = await get_db()
    existing = await db.execute("SELECT id FROM secrets WHERE name = ?", (body.name,))
    if await existing.fetchone():
        raise HTTPException(409, f"Secret '{body.name}' already exists")
    sid = f"sec_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO secrets (id, name, encrypted_value, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, body.name, body.value.encode("utf-8"), body.description, now, now),
    )
    await db.commit()
    return {"id": sid, "name": body.name}


@router.put("/{secret_name}")
async def update_secret(secret_name: str, body: SecretUpdate):
    db = await get_db()
    row = await db.execute("SELECT id FROM secrets WHERE name = ?", (secret_name,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Secret not found")
    fields, params = [], []
    if body.value is not None:
        fields.append("encrypted_value = ?")
        params.append(body.value.encode("utf-8"))
    if body.description is not None:
        fields.append("description = ?")
        params.append(body.description)
    if fields:
        fields.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(secret_name)
        await db.execute(f"UPDATE secrets SET {', '.join(fields)} WHERE name = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{secret_name}")
async def delete_secret(secret_name: str):
    db = await get_db()
    await db.execute("DELETE FROM secrets WHERE name = ?", (secret_name,))
    await db.commit()
    return {"ok": True}
