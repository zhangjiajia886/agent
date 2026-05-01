from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelConfigCreate(BaseModel):
    provider: str
    name: str
    model_id: str
    api_base: str = ""
    api_key_ref: str = ""
    is_default: bool = False
    max_tokens: int = 4096
    config: dict = {}


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    api_base: str | None = None
    api_key_ref: str | None = None
    is_default: bool | None = None
    max_tokens: int | None = None
    config: dict | None = None


@router.get("")
async def list_models(provider: str = ""):
    db = await get_db()
    query = "SELECT * FROM model_configs WHERE 1=1"
    params: list = []
    if provider:
        query += " AND provider = ?"
        params.append(provider)
    query += " ORDER BY provider, name"
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    result = [_row_to_model(r) for r in items]
    return {"items": result}


@router.post("")
async def create_model(body: ModelConfigCreate):
    db = await get_db()
    mid = f"model_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    if body.is_default:
        await db.execute("UPDATE model_configs SET is_default = 0 WHERE provider = ?", (body.provider,))
    await db.execute(
        "INSERT INTO model_configs (id, provider, name, model_id, api_base, api_key_ref, is_default, max_tokens, config, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mid, body.provider, body.name, body.model_id, body.api_base, body.api_key_ref, int(body.is_default), body.max_tokens, json.dumps(body.config), now, now),
    )
    await db.commit()
    return {"id": mid}


@router.put("/{model_id}")
async def update_model(model_id: str, body: ModelConfigUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.api_base is not None:
        fields.append("api_base = ?"); params.append(body.api_base)
    if body.api_key_ref is not None:
        fields.append("api_key_ref = ?"); params.append(body.api_key_ref)
    if body.is_default is not None:
        if body.is_default:
            row = await db.execute("SELECT provider FROM model_configs WHERE id = ?", (model_id,))
            item = await row.fetchone()
            if item:
                await db.execute("UPDATE model_configs SET is_default = 0 WHERE provider = ?", (item[0],))
        fields.append("is_default = ?"); params.append(int(body.is_default))
    if body.max_tokens is not None:
        fields.append("max_tokens = ?"); params.append(body.max_tokens)
    if body.config is not None:
        fields.append("config = ?"); params.append(json.dumps(body.config))
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(model_id)
        await db.execute(f"UPDATE model_configs SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    db = await get_db()
    await db.execute("DELETE FROM model_configs WHERE id = ?", (model_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{model_id}/set-default")
async def set_default_model(model_id: str):
    db = await get_db()
    row = await db.execute("SELECT provider FROM model_configs WHERE id = ?", (model_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Model not found")
    await db.execute("UPDATE model_configs SET is_default = 0 WHERE provider = ?", (item[0],))
    await db.execute("UPDATE model_configs SET is_default = 1 WHERE id = ?", (model_id,))
    await db.commit()
    return {"ok": True}


@router.get("/available")
async def list_available_models(request: Request):
    llm_client = request.app.state.llm_client
    models = await llm_client.list_models()
    return {"items": models}


def _row_to_model(row) -> dict:
    d = dict(row)
    if "config" in d and isinstance(d["config"], str):
        try:
            d["config"] = json.loads(d["config"])
        except Exception:
            pass
    d["is_default"] = bool(d.get("is_default", 0))
    return d
