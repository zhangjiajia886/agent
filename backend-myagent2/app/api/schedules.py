"""定时触发器 CRUD 接口（scheduled_triggers 表）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _row(r) -> dict:
    d = dict(r)
    if "inputs" in d and isinstance(d["inputs"], str):
        try:
            d["inputs"] = json.loads(d["inputs"])
        except Exception:
            pass
    return d


class ScheduleCreate(BaseModel):
    workflow_id: str
    name: str
    cron_expr: str
    timezone: str = "Asia/Shanghai"
    inputs: dict = {}
    app_id: str = ""
    created_by: str = ""


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expr: str | None = None
    timezone: str | None = None
    inputs: dict | None = None
    is_enabled: bool | None = None


@router.get("")
async def list_schedules(workflow_id: str = "", enabled_only: bool = False):
    db = await get_db()
    conds = []
    params: list = []
    if workflow_id:
        conds.append("workflow_id = ?")
        params.append(workflow_id)
    if enabled_only:
        conds.append("is_enabled = 1")
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    cur = await db.execute(
        f"SELECT * FROM scheduled_triggers {where} ORDER BY created_at DESC", params
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}


@router.post("")
async def create_schedule(body: ScheduleCreate):
    db = await get_db()
    # 验证工作流存在
    wf_cur = await db.execute("SELECT id FROM workflows WHERE id = ?", (body.workflow_id,))
    if not await wf_cur.fetchone():
        raise HTTPException(404, "Workflow not found")

    sid = f"sched_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO scheduled_triggers
           (id, workflow_id, app_id, created_by, name, cron_expr, timezone,
            inputs, is_enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (
            sid, body.workflow_id, body.app_id or None, body.created_by or None,
            body.name, body.cron_expr, body.timezone,
            json.dumps(body.inputs) if body.inputs else None,
            now, now,
        ),
    )
    await db.commit()
    return {"id": sid, "created_at": now}


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM scheduled_triggers WHERE id = ?", (schedule_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Schedule not found")
    return _row(row)


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.cron_expr is not None:
        fields.append("cron_expr = ?"); params.append(body.cron_expr)
    if body.timezone is not None:
        fields.append("timezone = ?"); params.append(body.timezone)
    if body.inputs is not None:
        fields.append("inputs = ?"); params.append(json.dumps(body.inputs))
    if body.is_enabled is not None:
        fields.append("is_enabled = ?"); params.append(1 if body.is_enabled else 0)
    if not fields:
        return {"ok": True}
    fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
    params.append(schedule_id)
    await db.execute(f"UPDATE scheduled_triggers SET {', '.join(fields)} WHERE id = ?", params)
    await db.commit()
    return {"ok": True}


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    db = await get_db()
    await db.execute("DELETE FROM scheduled_triggers WHERE id = ?", (schedule_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: str):
    """切换启用/禁用状态。"""
    db = await get_db()
    cur = await db.execute("SELECT is_enabled FROM scheduled_triggers WHERE id = ?", (schedule_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Schedule not found")
    current = row["is_enabled"] if isinstance(row, dict) else row[0]
    new_val = 0 if current else 1
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE scheduled_triggers SET is_enabled = ?, updated_at = ? WHERE id = ?",
        (new_val, now, schedule_id),
    )
    await db.commit()
    return {"ok": True, "is_enabled": bool(new_val)}
