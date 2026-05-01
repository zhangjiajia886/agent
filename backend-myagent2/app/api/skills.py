from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    content: str = ""
    tags: list[str] = []
    is_builtin: bool = False
    source_type: str = "user"
    source_path: str = ""
    source_repo: str = ""
    allowed_tools: list[str] = []
    arguments: list[str] = []
    argument_hint: str = ""
    when_to_use: str = ""
    context_mode: str = ""
    agent: str = ""
    model: str = ""
    variables: list[str] = []
    required_tools: list[str] = []
    migration_status: str = ""
    migration_notes: str = ""
    content_hash: str = ""


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    is_builtin: bool | None = None
    source_type: str | None = None
    source_path: str | None = None
    source_repo: str | None = None
    allowed_tools: list[str] | None = None
    arguments: list[str] | None = None
    argument_hint: str | None = None
    when_to_use: str | None = None
    context_mode: str | None = None
    agent: str | None = None
    model: str | None = None
    variables: list[str] | None = None
    required_tools: list[str] | None = None
    migration_status: str | None = None
    migration_notes: str | None = None
    content_hash: str | None = None


@router.get("")
async def list_skills(
    category: str = "",
    search: str = "",
    source_type: str = "",
    migration_status: str = "",
    context_mode: str = "",
):
    db = await get_db()
    query = "SELECT * FROM skills WHERE 1=1"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if migration_status:
        query += " AND migration_status = ?"
        params.append(migration_status)
    if context_mode:
        query += " AND context_mode = ?"
        params.append(context_mode)
    query += " ORDER BY updated_at DESC"
    rows = await db.execute(query, params)
    items = await rows.fetchall()
    return {"items": [_row(r) for r in items]}


@router.post("")
async def create_skill(body: SkillCreate):
    db = await get_db()
    sid = f"skill_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO skills
           (id, name, description, category, content, tags, is_builtin,
            source_type, source_path, source_repo,
            allowed_tools, arguments, argument_hint, when_to_use,
            context_mode, agent, model,
            variables, required_tools,
            migration_status, migration_notes, content_hash,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?, ?,?,?, ?,?)""",
        (sid, body.name, body.description, body.category, body.content,
         json.dumps(body.tags), int(body.is_builtin),
         body.source_type, body.source_path, body.source_repo,
         json.dumps(body.allowed_tools), json.dumps(body.arguments),
         body.argument_hint, body.when_to_use,
         body.context_mode, body.agent, body.model,
         json.dumps(body.variables), json.dumps(body.required_tools),
         body.migration_status, body.migration_notes, body.content_hash,
         now, now),
    )
    await db.commit()
    return {"id": sid, "name": body.name}


@router.get("/stats")
async def skill_stats():
    db = await get_db()
    by_source = await db.execute(
        "SELECT source_type, COUNT(*) as cnt FROM skills GROUP BY source_type")
    by_status = await db.execute(
        "SELECT migration_status, COUNT(*) as cnt FROM skills GROUP BY migration_status")
    by_mode = await db.execute(
        "SELECT context_mode, COUNT(*) as cnt FROM skills GROUP BY context_mode")
    total = await db.execute("SELECT COUNT(*) as cnt FROM skills")
    return {
        "total": (await total.fetchone())["cnt"],
        "by_source_type": {r["source_type"]: r["cnt"] for r in await by_source.fetchall()},
        "by_migration_status": {r["migration_status"]: r["cnt"] for r in await by_status.fetchall()},
        "by_context_mode": {r["context_mode"]: r["cnt"] for r in await by_mode.fetchall()},
    }


@router.post("/import")
async def import_skills(body: list[SkillCreate]):
    """批量导入, 按 name + source_type 幂等"""
    db = await get_db()
    inserted, skipped = 0, 0
    now = datetime.now(timezone.utc).isoformat()
    for sk in body:
        exists = await db.execute(
            "SELECT id FROM skills WHERE name = ? AND source_type = ?",
            (sk.name, sk.source_type))
        if await exists.fetchone():
            skipped += 1
            continue
        sid = f"skill_{uuid.uuid4().hex[:12]}"
        ch = sk.content_hash or hashlib.sha256(sk.content.encode()).hexdigest()[:16]
        await db.execute(
            """INSERT INTO skills
               (id,name,description,category,content,tags,is_builtin,
                source_type,source_path,source_repo,
                allowed_tools,arguments,argument_hint,when_to_use,
                context_mode,agent,model,
                variables,required_tools,
                migration_status,migration_notes,content_hash,
                created_at,updated_at)
               VALUES (?,?,?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?, ?,?,?, ?,?)""",
            (sid, sk.name, sk.description, sk.category, sk.content,
             json.dumps(sk.tags), int(sk.is_builtin),
             sk.source_type, sk.source_path, sk.source_repo,
             json.dumps(sk.allowed_tools), json.dumps(sk.arguments),
             sk.argument_hint, sk.when_to_use,
             sk.context_mode, sk.agent, sk.model,
             json.dumps(sk.variables), json.dumps(sk.required_tools),
             sk.migration_status, sk.migration_notes, ch,
             now, now),
        )
        inserted += 1
    await db.commit()
    return {"inserted": inserted, "skipped": skipped}


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
    item = await row.fetchone()
    if not item:
        raise HTTPException(404, "Skill not found")
    return _row(item)


@router.put("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpdate):
    db = await get_db()
    fields, params = [], []
    if body.name is not None:
        fields.append("name = ?"); params.append(body.name)
    if body.description is not None:
        fields.append("description = ?"); params.append(body.description)
    if body.category is not None:
        fields.append("category = ?"); params.append(body.category)
    if body.content is not None:
        fields.append("content = ?"); params.append(body.content)
    if body.tags is not None:
        fields.append("tags = ?"); params.append(json.dumps(body.tags))
    if body.is_builtin is not None:
        fields.append("is_builtin = ?"); params.append(int(body.is_builtin))
    for attr in ("source_type", "source_path", "source_repo", "argument_hint",
                 "when_to_use", "context_mode", "agent", "model",
                 "migration_status", "migration_notes", "content_hash"):
        val = getattr(body, attr, None)
        if val is not None:
            fields.append(f"{attr} = ?"); params.append(val)
    for attr in ("allowed_tools", "arguments", "variables", "required_tools"):
        val = getattr(body, attr, None)
        if val is not None:
            fields.append(f"{attr} = ?"); params.append(json.dumps(val))
    if fields:
        fields.append("updated_at = ?"); params.append(datetime.now(timezone.utc).isoformat())
        params.append(skill_id)
        await db.execute(f"UPDATE skills SET {', '.join(fields)} WHERE id = ?", params)
        await db.commit()
    return {"ok": True}


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    db = await get_db()
    await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{skill_id}/invoke")
async def invoke_skill(skill_id: str, body: dict | None = None):
    """记录一次 skill 调用"""
    db = await get_db()
    row = await db.execute("SELECT id FROM skills WHERE id = ?", (skill_id,))
    if not await row.fetchone():
        raise HTTPException(404, "Skill not found")
    body = body or {}
    inv_id = f"inv_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO skill_invocations
           (id, skill_id, session_id, execution_mode, args_text,
            status, duration_ms, result_preview, invoked_at)
           VALUES (?,?,?,?,?, ?,?,?,?)""",
        (inv_id, skill_id,
         body.get("session_id", ""),
         body.get("execution_mode", ""),
         body.get("args_text", ""),
         body.get("status", "success"),
         body.get("duration_ms", 0),
         body.get("result_preview", ""),
         now),
    )
    await db.commit()
    return {"id": inv_id}


@router.get("/{skill_id}/invocations")
async def list_invocations(skill_id: str, limit: int = 50):
    """获取 skill 调用历史"""
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM skill_invocations WHERE skill_id = ? ORDER BY invoked_at DESC LIMIT ?",
        (skill_id, limit))
    items = [dict(r) for r in await rows.fetchall()]
    return {"items": items}


def _row(r) -> dict:
    d = dict(r)
    for k in ("tags", "allowed_tools", "arguments", "variables", "required_tools"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    d["is_builtin"] = bool(d.get("is_builtin", 0))
    return d
