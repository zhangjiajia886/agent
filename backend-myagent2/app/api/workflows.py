from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..db.database import get_db
from ..core.cancellation import CancellationToken

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# In-memory store for running executions' cancel tokens
_running_executions: dict[str, CancellationToken] = {}


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    definition: dict = {}
    tags: list[str] = []
    status: str = "draft"


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None
    tags: list[str] | None = None
    status: str | None = None


class ExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}


@router.get("")
async def list_workflows(
    search: str = "",
    status: str = "",
    skip: int = 0,
    limit: int = 50,
):
    db = await get_db()
    query = "SELECT * FROM workflows WHERE 1=1"
    params: list = []
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    count_q = "SELECT COUNT(*) AS cnt FROM workflows WHERE 1=1"
    count_params: list = []
    if search:
        count_q += " AND (name LIKE ? OR description LIKE ?)"
        count_params.extend([f"%{search}%", f"%{search}%"])
    if status:
        count_q += " AND status = ?"
        count_params.append(status)
    count_row = await db.execute(count_q, count_params)
    total = (await count_row.fetchone())["cnt"]
    return {
        "items": [_row_to_dict(r) for r in items],
        "total": total,
    }


@router.post("")
async def create_workflow(body: WorkflowCreate):
    db = await get_db()
    wf_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO workflows (id, name, description, definition, status, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (wf_id, body.name, body.description, json.dumps(body.definition), body.status, json.dumps(body.tags), now, now),
    )
    await db.commit()
    return {"id": wf_id, "name": body.name, "status": body.status}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Workflow not found")
    return _row_to_dict(item)


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate):
    db = await get_db()
    row = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    existing = await row.fetchone()
    if not existing:
        raise HTTPException(404, "Workflow not found")

    fields = []
    params = []
    if body.name is not None:
        fields.append("name = ?")
        params.append(body.name)
    if body.description is not None:
        fields.append("description = ?")
        params.append(body.description)
    if body.definition is not None:
        fields.append("definition = ?")
        params.append(json.dumps(body.definition))
        fields.append("version = version + 1")
    if body.tags is not None:
        fields.append("tags = ?")
        params.append(json.dumps(body.tags))
    if body.status is not None:
        fields.append("status = ?")
        params.append(body.status)

    if fields:
        fields.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(workflow_id)
        await db.execute(f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()

    return {"ok": True}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    db = await get_db()
    await db.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{workflow_id}/clone")
async def clone_workflow(workflow_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Workflow not found")
    d = _row_to_dict(item)
    new_id = f"wf_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO workflows (id, name, description, definition, status, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (new_id, d["name"] + " (copy)", d["description"], json.dumps(d["definition"]), "draft", json.dumps(d.get("tags", [])), now, now),
    )
    await db.commit()
    return {"id": new_id}


@router.get("/{workflow_id}/versions")
async def list_versions(workflow_id: str):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version DESC",
        (workflow_id,),
    )
    items = await rows.fetchall()
    return {"items": [_row_to_dict(r) for r in items]}


@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, body: ExecuteRequest, request: Request):
    db = await get_db()
    row = await db.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Workflow not found")

    wf = _row_to_dict(item)
    definition = wf["definition"]
    exec_id = f"exec_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "INSERT INTO executions (id, workflow_id, workflow_name, status, inputs, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (exec_id, workflow_id, wf["name"], "running", json.dumps(body.inputs), now, now),
    )
    await db.commit()

    cancel_token = CancellationToken()
    _running_executions[exec_id] = cancel_token

    engine = request.app.state.engine
    asyncio.create_task(_run_execution(db, exec_id, engine, definition, body.inputs, cancel_token))

    return {"execution_id": exec_id, "status": "running"}


async def _run_execution(db, exec_id, engine, definition, inputs, cancel_token):
    try:
        result = await engine.execute(exec_id, definition, inputs, cancel_token)
        status = result.get("status", "done")
        now = datetime.now(timezone.utc).isoformat()
        trace_spans = result.get("trace_spans", []) or []
        logs = [
            {
                "type": "node",
                "node_id": span.get("node_id", ""),
                "node_type": span.get("node_type", ""),
                "status": span.get("status", ""),
                "started_at": span.get("start_time", ""),
                "ended_at": span.get("end_time", ""),
                "latency_ms": span.get("latency_ms", 0),
                "result_preview": span.get("result_preview", ""),
                "error": span.get("error", ""),
            }
            for span in trace_spans
        ]
        await db.execute(
            "UPDATE executions SET status = ?, outputs = ?, node_statuses = ?, logs = ?, finished_at = ? WHERE id = ?",
            (status, json.dumps(result.get("outputs", {})), json.dumps(result.get("node_statuses", {})), json.dumps(logs), now, exec_id),
        )
        await db.execute("DELETE FROM trace_spans WHERE execution_id = ?", (exec_id,))
        for span in trace_spans:
            await db.execute(
                """INSERT INTO trace_spans
                   (id, execution_id, parent_span_id, node_id, node_type, status, start_time, end_time, model, input_tokens, output_tokens, latency_ms, tool_name, tool_duration_ms, result_preview, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span.get("span_id") or f"span_{uuid.uuid4().hex[:12]}",
                    exec_id,
                    span.get("parent_span_id"),
                    span.get("node_id", ""),
                    span.get("node_type", ""),
                    span.get("status", "running"),
                    span.get("start_time", now),
                    span.get("end_time"),
                    span.get("model"),
                    span.get("input_tokens", 0),
                    span.get("output_tokens", 0),
                    span.get("latency_ms", 0),
                    span.get("tool_name"),
                    span.get("tool_duration_ms", 0),
                    span.get("result_preview", ""),
                    span.get("error", ""),
                ),
            )
        await db.commit()
    except Exception as e:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE executions SET status = 'error', error = ?, finished_at = ? WHERE id = ?",
            (str(e), now, exec_id),
        )
        await db.commit()
    finally:
        _running_executions.pop(exec_id, None)


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    for key in ("definition", "tags", "inputs", "outputs", "node_statuses", "logs"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
