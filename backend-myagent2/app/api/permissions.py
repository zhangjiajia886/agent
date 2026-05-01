from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/permissions", tags=["permissions"])

DEFAULT_POLICIES = {
    "bash":         "always_ask",
    "python_exec":  "always_ask",
    "write_file":   "always_ask",
    "read_file":    "auto_allow",
    "grep_search":  "auto_allow",
    "http_request": "always_ask",
}


class PermissionCreate(BaseModel):
    tool_name: str
    policy: str = "always_ask"
    conditions: dict = {}
    description: str = ""
    priority: int = 0
    is_enabled: bool = True


class PermissionUpdate(BaseModel):
    policy: str | None = None
    conditions: dict | None = None
    description: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None


@router.get("")
async def list_permissions():
    db = await get_db()
    rows = await db.execute("SELECT * FROM permissions ORDER BY priority DESC, tool_name")
    items = await rows.fetchall()
    return {"items": [_row(r) for r in items], "defaults": DEFAULT_POLICIES}


@router.post("")
async def create_permission(body: PermissionCreate):
    db = await get_db()
    pid = f"perm_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO permissions (id, tool_name, policy, conditions, description, priority, is_enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, body.tool_name, body.policy, json.dumps(body.conditions), body.description, body.priority, int(body.is_enabled), now),
    )
    await db.commit()
    return {"id": pid}


@router.put("/{perm_id}")
async def update_permission(perm_id: str, body: PermissionUpdate):
    db = await get_db()
    fields, params = [], []
    if body.policy is not None:
        fields.append("policy = ?"); params.append(body.policy)
    if body.conditions is not None:
        fields.append("conditions = ?"); params.append(json.dumps(body.conditions))
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.priority is not None:
        fields.append("priority = ?"); params.append(body.priority)
    if body.is_enabled is not None:
        fields.append("is_enabled = ?"); params.append(int(body.is_enabled))
    if fields:
        params.append(perm_id)
        await db.execute(f"UPDATE permissions SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{perm_id}")
async def delete_permission(perm_id: str):
    db = await get_db()
    await db.execute("DELETE FROM permissions WHERE id = ?", (perm_id,))
    await db.commit()
    return {"ok": True}


@router.post("/reset-defaults")
async def reset_defaults():
    db = await get_db()
    await db.execute("DELETE FROM permissions")
    now = datetime.now(timezone.utc).isoformat()
    for tool_name, policy in DEFAULT_POLICIES.items():
        pid = f"perm_{uuid.uuid4().hex[:12]}"
        await db.execute(
            "INSERT INTO permissions (id, tool_name, policy, conditions, description, priority, is_enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, tool_name, policy, "{}", f"Default policy for {tool_name}", 0, 1, now),
        )
    await db.commit()
    return {"ok": True}


def _row(r) -> dict:
    d = dict(r)
    if "conditions" in d and isinstance(d["conditions"], str):
        try:
            d["conditions"] = json.loads(d["conditions"])
        except Exception:
            pass
    d["is_enabled"] = bool(d.get("is_enabled", 0))
    return d
