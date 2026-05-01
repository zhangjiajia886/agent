from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPServerCreate(BaseModel):
    name: str
    command: str
    args: list[str] = []
    env: dict[str, str] = {}
    auto_start: bool = False


class MCPServerUpdate(BaseModel):
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    auto_start: bool | None = None


@router.get("")
async def list_mcp_servers():
    db = await get_db()
    rows = await db.execute("SELECT * FROM mcp_servers ORDER BY name")
    items = await rows.fetchall()
    return {"items": [_row(r) for r in items]}


@router.post("")
async def create_mcp_server(body: MCPServerCreate):
    db = await get_db()
    existing = await db.execute("SELECT id FROM mcp_servers WHERE name = ?", (body.name,))
    if await existing.fetchone():
        raise HTTPException(409, f"MCP server '{body.name}' already exists")
    sid = f"mcp_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO mcp_servers (id, name, command, args, env, auto_start, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, body.name, body.command, json.dumps(body.args), json.dumps(body.env), int(body.auto_start), "disconnected", now, now),
    )
    await db.commit()
    return {"id": sid, "name": body.name}


@router.get("/{server_id}")
async def get_mcp_server(server_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "MCP server not found")
    return _row(item)


@router.put("/{server_id}")
async def update_mcp_server(server_id: str, body: MCPServerUpdate):
    db = await get_db()
    fields, params = [], []
    if body.command is not None:
        fields.append("command = ?"); params.append(body.command)
    if body.args is not None:
        fields.append("args = ?"); params.append(json.dumps(body.args))
    if body.env is not None:
        fields.append("env = ?"); params.append(json.dumps(body.env))
    if body.auto_start is not None:
        fields.append("auto_start = ?"); params.append(int(body.auto_start))
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(server_id)
        await db.execute(f"UPDATE mcp_servers SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{server_id}")
async def delete_mcp_server(server_id: str):
    db = await get_db()
    await db.execute("DELETE FROM mcp_servers WHERE id = ?", (server_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{server_id}/connect")
async def connect_server(server_id: str):
    db = await get_db()
    await db.execute(
        "UPDATE mcp_servers SET status = 'connected', updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), server_id),
    )
    await db.commit()
    return {"ok": True, "status": "connected"}


@router.post("/{server_id}/disconnect")
async def disconnect_server(server_id: str):
    db = await get_db()
    await db.execute(
        "UPDATE mcp_servers SET status = 'disconnected', updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), server_id),
    )
    await db.commit()
    return {"ok": True, "status": "disconnected"}


def _row(r) -> dict:
    d = dict(r)
    for k in ("args", "env", "tools"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    d["auto_start"] = bool(d.get("auto_start", 0))
    return d
