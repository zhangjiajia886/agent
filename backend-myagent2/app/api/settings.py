from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

from ..db.database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS: dict[str, Any] = {
    "general.language": "zh-CN",
    "general.theme": "system",
    "llm.default_model": "qwen3-32b",
    "llm.default_temperature": 0.7,
    "llm.default_max_tokens": 2048,
    "execution.max_concurrent_workflows": 3,
    "execution.max_concurrent_llm_calls": 2,
    "execution.default_timeout": 300,
    "security.sandbox_mode": "subprocess",
    "security.enable_command_blacklist": True,
    "ui.show_token_usage": True,
    "ui.show_cost_estimation": True,
    "ui.auto_save_interval": 30,
}


class SettingUpdate(BaseModel):
    value: Any


@router.get("")
async def list_settings():
    db = await get_db()
    rows = await db.execute("SELECT * FROM settings ORDER BY key")
    items = await rows.fetchall()
    stored = {}
    for r in items:
        d = dict(r)
        try:
            d["value"] = json.loads(d["value"])
        except Exception:
            pass
        stored[d["key"]] = d["value"]
    merged = {**DEFAULTS, **stored}
    return {"items": merged, "defaults": DEFAULTS}


@router.get("/{key:path}")
async def get_setting(key: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM settings WHERE key = ?", (key,))
    item = await row.fetchone()
    if item:
        d = dict(item)
        try:
            d["value"] = json.loads(d["value"])
        except Exception:
            pass
        return d
    if key in DEFAULTS:
        return {"key": key, "value": DEFAULTS[key]}
    return {"key": key, "value": None}


@router.put("/{key:path}")
async def update_setting(key: str, body: SettingUpdate):
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(body.value), now),
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{key:path}")
async def delete_setting(key: str):
    db = await get_db()
    await db.execute("DELETE FROM settings WHERE key = ?", (key,))
    await db.commit()
    return {"ok": True}


@router.post("/reset")
async def reset_settings():
    db = await get_db()
    await db.execute("DELETE FROM settings")
    await db.commit()
    return {"ok": True, "defaults": DEFAULTS}
