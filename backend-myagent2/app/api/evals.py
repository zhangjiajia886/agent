"""评测框架 CRUD 接口（eval_datasets / eval_cases / eval_runs / eval_results）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/evals", tags=["evals"])


def _row(r) -> dict:
    return dict(r)


# ── Pydantic Models ──────────────────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    app_id: str = ""
    created_by: str = ""


class CaseCreate(BaseModel):
    dataset_id: str
    question: str
    expected_answer: str = ""
    context: str = ""
    tags: str = ""
    difficulty: str = "medium"


class RunCreate(BaseModel):
    dataset_id: str
    app_id: str = ""
    model: str = ""
    label: str = ""


# ── Datasets ─────────────────────────────────────────────────────────────────

@router.get("/datasets")
async def list_datasets(app_id: str = ""):
    db = await get_db()
    if app_id:
        cur = await db.execute(
            "SELECT * FROM eval_datasets WHERE app_id = ? ORDER BY created_at DESC", (app_id,)
        )
    else:
        cur = await db.execute("SELECT * FROM eval_datasets ORDER BY created_at DESC")
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}


@router.post("/datasets")
async def create_dataset(body: DatasetCreate):
    db = await get_db()
    did = f"ds_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO eval_datasets (id, name, description, app_id, created_by, created_at) VALUES (?,?,?,?,?,?)",
        (did, body.name, body.description, body.app_id or None, body.created_by or None, now),
    )
    await db.commit()
    return {"id": did, "created_at": now}


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    db = await get_db()
    await db.execute("DELETE FROM eval_datasets WHERE id = ?", (dataset_id,))
    await db.commit()
    return {"ok": True}


# ── Cases ─────────────────────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id}/cases")
async def list_cases(dataset_id: str, limit: int = 100, offset: int = 0):
    db = await get_db()
    count_cur = await db.execute(
        "SELECT COUNT(*) FROM eval_cases WHERE dataset_id = ?", (dataset_id,)
    )
    count_row = await count_cur.fetchone()
    total = (count_row[0] if isinstance(count_row, (list, tuple)) else count_row["COUNT(*)"]) or 0
    cur = await db.execute(
        "SELECT * FROM eval_cases WHERE dataset_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
        (dataset_id, limit, offset),
    )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows], "total": total}


@router.post("/cases")
async def create_case(body: CaseCreate):
    db = await get_db()
    ds_cur = await db.execute("SELECT id FROM eval_datasets WHERE id = ?", (body.dataset_id,))
    if not await ds_cur.fetchone():
        raise HTTPException(404, "Dataset not found")
    cid = f"case_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO eval_cases
           (id, dataset_id, question, expected_answer, context, tags, difficulty, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (cid, body.dataset_id, body.question, body.expected_answer,
         body.context, body.tags, body.difficulty, now),
    )
    await db.commit()
    return {"id": cid, "created_at": now}


@router.delete("/cases/{case_id}")
async def delete_case(case_id: str):
    db = await get_db()
    await db.execute("DELETE FROM eval_cases WHERE id = ?", (case_id,))
    await db.commit()
    return {"ok": True}


# ── Runs ──────────────────────────────────────────────────────────────────────

@router.get("/runs")
async def list_runs(dataset_id: str = "", limit: int = 50):
    db = await get_db()
    if dataset_id:
        cur = await db.execute(
            "SELECT * FROM eval_runs WHERE dataset_id = ? ORDER BY created_at DESC LIMIT ?",
            (dataset_id, limit),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    rows = await cur.fetchall()
    return {"items": [_row(r) for r in rows]}


@router.post("/runs")
async def create_run(body: RunCreate):
    db = await get_db()
    ds_cur = await db.execute("SELECT id FROM eval_datasets WHERE id = ?", (body.dataset_id,))
    if not await ds_cur.fetchone():
        raise HTTPException(404, "Dataset not found")

    count_cur = await db.execute(
        "SELECT COUNT(*) FROM eval_cases WHERE dataset_id = ?", (body.dataset_id,)
    )
    count_row = await count_cur.fetchone()
    total = (count_row[0] if isinstance(count_row, (list, tuple)) else count_row["COUNT(*)"]) or 0

    rid = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO eval_runs
           (id, dataset_id, app_id, model, label, status, total_cases, created_at)
           VALUES (?,?,?,?,?,'pending',?,?)""",
        (rid, body.dataset_id, body.app_id or None, body.model,
         body.label, total, now),
    )
    await db.commit()
    return {"id": rid, "total_cases": total, "created_at": now}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Run not found")
    result = _row(row)
    # 附带结果列表
    res_cur = await db.execute(
        "SELECT * FROM eval_results WHERE run_id = ? ORDER BY id", (run_id,)
    )
    result["results"] = [_row(r) for r in await res_cur.fetchall()]
    return result


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    db = await get_db()
    await db.execute("DELETE FROM eval_runs WHERE id = ?", (run_id,))
    await db.commit()
    return {"ok": True}
