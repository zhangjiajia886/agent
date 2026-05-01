from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..db.database import get_db, _db_type as _DB_TYPE
from ..core.auth import get_current_user_optional
from .chat import _extract_thinking

router = APIRouter(prefix="/api/apps", tags=["apps"])


# ── Pydantic models ──────────────────────────────────────────────────────────

class AppCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "🤖"
    opening_msg: str = ""
    system_prompt: str = ""
    variables: list[dict] = []
    tools: list[str] = []
    model: str = ""
    model_params: dict = {}


class AppUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    opening_msg: str | None = None
    system_prompt: str | None = None
    variables: list[dict] | None = None
    tools: list[str] | None = None
    model: str | None = None
    model_params: dict | None = None
    is_published: bool | None = None


class ChatBody(BaseModel):
    content: str
    session_id: str | None = None
    var_values: dict = {}


class PreviewChatBody(BaseModel):
    content: str
    session_id: str | None = None
    var_values: dict = {}
    app_config: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(r) -> dict:
    d = dict(r)
    for k in ("variables", "tools"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                d[k] = []
    if "model_params" in d and isinstance(d["model_params"], str):
        try:
            d["model_params"] = json.loads(d["model_params"])
        except Exception:
            d["model_params"] = {}
    d["is_published"] = bool(d.get("is_published", 0))
    return d


def _msg_row(r) -> dict:
    d = dict(r)
    for k in ("tool_calls", "metadata"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


async def _build_system_prompt(db, app: dict, var_values: dict) -> str:
    prompt = app.get("system_prompt", "")
    # inject variable values
    for key, value in var_values.items():
        prompt = re.sub(r"\{\{" + re.escape(str(key)) + r"\}\}", str(value), prompt)
    return prompt


async def _get_or_create_session(
    db, app_id: str, session_id: str | None, user_id: str | None = None
) -> str:
    if session_id:
        row = await db.execute("SELECT id FROM app_sessions WHERE id=? AND app_id=?", (session_id, app_id))
        existing = await row.fetchone()
        if existing:
            return session_id
    sid = f"appsess_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO app_sessions (id,app_id,user_id,title,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (sid, app_id, user_id, "新对话", now, now),
    )
    await db.commit()
    return sid


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_apps():
    db = await get_db()
    rows = await db.execute("SELECT * FROM apps ORDER BY updated_at DESC")
    return {"items": [_row(r) for r in await rows.fetchall()]}


@router.post("")
async def create_app(body: AppCreate):
    db = await get_db()
    app_id = f"app_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO apps (id,name,description,icon,opening_msg,system_prompt,variables,tools,model,model_params,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (app_id, body.name, body.description, body.icon, body.opening_msg,
         body.system_prompt, json.dumps(body.variables), json.dumps(body.tools),
         body.model, json.dumps(body.model_params), now, now),
    )
    await db.commit()
    row = await db.execute("SELECT * FROM apps WHERE id=?", (app_id,))
    return _row(await row.fetchone())


@router.get("/{app_id}")
async def get_app(app_id: str):
    db = await get_db()
    row = await db.execute("SELECT * FROM apps WHERE id=?", (app_id,))
    app = await row.fetchone()
    if not app:
        raise HTTPException(404, "App not found")
    return _row(app)


@router.put("/{app_id}")
async def update_app(app_id: str, body: AppUpdate):
    db = await get_db()
    fields, params = [], []
    for col, val in [
        ("name", body.name), ("description", body.description),
        ("icon", body.icon), ("opening_msg", body.opening_msg),
        ("system_prompt", body.system_prompt), ("model", body.model),
    ]:
        if val is not None:
            fields.append(f"{col}=?"); params.append(val)
    for col, val in [("variables", body.variables), ("tools", body.tools)]:
        if val is not None:
            fields.append(f"{col}=?"); params.append(json.dumps(val))
    if body.model_params is not None:
        fields.append("model_params=?"); params.append(json.dumps(body.model_params))
    if body.is_published is not None:
        fields.append("is_published=?"); params.append(1 if body.is_published else 0)
    if fields:
        fields.append("updated_at=?")
        params.extend([datetime.now(timezone.utc).isoformat(), app_id])
        await db.execute(f"UPDATE apps SET {', '.join(fields)} WHERE id=?", params)
        await db.commit()
    row = await db.execute("SELECT * FROM apps WHERE id=?", (app_id,))
    return _row(await row.fetchone())


@router.delete("/{app_id}")
async def delete_app(app_id: str):
    db = await get_db()
    await db.execute(
        "DELETE FROM app_messages WHERE session_id IN (SELECT id FROM app_sessions WHERE app_id=?)", (app_id,)
    )
    await db.execute("DELETE FROM app_sessions WHERE app_id=?", (app_id,))
    await db.execute("DELETE FROM apps WHERE id=?", (app_id,))
    await db.commit()
    return {"ok": True}


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/{app_id}/sessions")
async def list_sessions(app_id: str):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM app_sessions WHERE app_id=? ORDER BY updated_at DESC", (app_id,)
    )
    return {"items": [dict(r) for r in await rows.fetchall()]}


@router.post("/{app_id}/sessions")
async def create_session(app_id: str):
    db = await get_db()
    sid = f"appsess_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO app_sessions (id,app_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
        (sid, app_id, "新对话", now, now),
    )
    await db.commit()
    return {"id": sid, "app_id": app_id, "title": "新对话", "created_at": now}


@router.get("/{app_id}/sessions/{session_id}/messages")
async def get_messages(app_id: str, session_id: str):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM app_messages WHERE session_id=? ORDER BY created_at", (session_id,)
    )
    return {"items": [_msg_row(r) for r in await rows.fetchall()]}


# ── Streaming Chat ────────────────────────────────────────────────────────────

@router.post("/{app_id}/sessions/{session_id}/chat")
async def chat(
    app_id: str, session_id: str, body: ChatBody, request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
):
    _uid = current_user["sub"] if current_user else None
    db = await get_db()
    row = await db.execute("SELECT * FROM apps WHERE id=?", (app_id,))
    app = await row.fetchone()
    if not app:
        raise HTTPException(404, "App not found")
    app_dict = _row(app)

    system_prompt = await _build_system_prompt(db, app_dict, body.var_values)
    allowed_tools = app_dict.get("tools", []) or None

    model_params = app_dict.get("model_params") or {}
    if isinstance(model_params, str):
        try:
            model_params = json.loads(model_params)
        except Exception:
            model_params = {}

    return StreamingResponse(
        _stream_chat(request, db, session_id, body.content, system_prompt,
                     app_dict.get("model", ""), allowed_tools, model_params=model_params,
                     current_user_id=_uid),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{app_id}/preview/chat")
async def preview_chat(app_id: str, body: PreviewChatBody, request: Request):
    """Real-time preview during building — uses in-request config, not saved DB values."""
    db = await get_db()
    cfg = body.app_config or {}
    system_prompt = await _build_system_prompt(db, cfg, body.var_values)
    allowed_tools = cfg.get("tools", []) or None
    session_id = body.session_id or f"preview_{uuid.uuid4().hex[:8]}"

    cfg_model_params = cfg.get("model_params") or {}
    if isinstance(cfg_model_params, str):
        try:
            cfg_model_params = json.loads(cfg_model_params)
        except Exception:
            cfg_model_params = {}

    return StreamingResponse(
        _stream_chat(request, db, session_id, body.content, system_prompt,
                     cfg.get("model", ""), allowed_tools, save_messages=False,
                     model_params=cfg_model_params),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


MAX_APP_HISTORY_ROUNDS = 10   # keep last 10 turns (user+assistant pairs)
MAX_HISTORY_CHARS = 12000     # rough budget: ~3000 tokens, leave room for system prompt + response


async def _load_app_history(db, session_id: str) -> list[dict]:
    """Load conversation history from app_messages, trimmed to fit token budget."""
    rows = await db.execute(
        """SELECT role, content FROM app_messages
           WHERE session_id = ? AND role IN ('user','assistant')
           ORDER BY created_at DESC LIMIT ?""",
        (session_id, MAX_APP_HISTORY_ROUNDS * 2),
    )
    items = await rows.fetchall()
    messages = [{"role": r["role"], "content": r["content"] or ""} for r in reversed(items)]

    # Trim from oldest until total chars fit within budget
    while messages:
        total = sum(len(m["content"]) for m in messages)
        if total <= MAX_HISTORY_CHARS:
            break
        messages.pop(0)  # remove oldest message

    return messages


async def _stream_chat(request, db, session_id: str, user_content: str,
                       system_prompt: str, model: str, allowed_tools: list | None,
                       save_messages: bool = True, model_params: dict | None = None,
                       current_user_id: str | None = None):
    from ..agent.loop import AgentLoop

    now = datetime.now(timezone.utc).isoformat()

    # Load history BEFORE saving current user message
    history = await _load_app_history(db, session_id) if save_messages else []

    if save_messages:
        user_msg_id = f"appmsg_{uuid.uuid4().hex[:12]}"
        await db.execute(
            "INSERT INTO app_messages (id,session_id,role,content,created_at) VALUES (?,?,?,?,?)",
            (user_msg_id, session_id, "user", user_content, now),
        )
        await db.commit()

    _mp = model_params or {}
    _temperature = float(_mp.get("temperature", 0.7))
    _max_tokens = int(_mp.get("max_tokens", 2048))
    _enable_thinking = bool(_mp.get("enable_thinking", False))

    agent = AgentLoop(
        llm=request.app.state.llm_client,
        tools=request.app.state.tool_registry,
    )

    full_content = ""   # current round's raw delta (reset each round; DB saves last round)
    prior_clean = ""    # accumulated clean text from all previous tool-call rounds
    tool_calls_data = []
    in_tool_round = False  # True while we're between tool_calls and next delta round
    _done_meta: dict = {}

    try:
        async for event in agent.run(
            temperature=_temperature, max_tokens=_max_tokens,
            enable_thinking=_enable_thinking,
            session_id=session_id,
            user_content=user_content,
            model_override=model,
            system_prompt_override=system_prompt,
            allowed_tools=allowed_tools,
            history_override=history,
        ):
            etype = event.get("type", "")
            if etype == "delta":
                if in_tool_round:
                    # First delta of a new round — reset raw accumulator
                    full_content = ""
                    in_tool_round = False
                full_content += event.get("content", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif etype == "done":
                _done_meta = event.get("metadata", {})
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif etype == "tool_calls":
                tool_calls_data = event.get("tool_calls", [])
                in_tool_round = True
                # Accumulate clean text from this round into prior_clean
                clean = event.get("clean_text", "")
                if clean:
                    prior_clean = (prior_clean.rstrip() + "\n\n" + clean).lstrip() if prior_clean else clean
                # Only send content_replace when there is content — never send empty string
                # (an empty content_replace would wipe everything the user already sees)
                if prior_clean:
                    replace_evt = {"type": "content_replace", "content": prior_clean}
                    yield f"data: {json.dumps(replace_evt, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if save_messages:
            finish_time = datetime.now(timezone.utc).isoformat()
            asst_msg_id = f"appmsg_{uuid.uuid4().hex[:12]}"
            extracted_thinking, clean_answer = _extract_thinking(full_content)
            await db.execute(
                """INSERT INTO app_messages
                   (id, session_id, role, content, thinking_content,
                    model, input_tokens, output_tokens, latency_ms, tool_rounds,
                    tool_calls, created_at)
                   VALUES (?, ?, 'assistant', ?, ?,  ?, ?, ?, ?, ?,  ?, ?)""",
                (
                    asst_msg_id, session_id,
                    clean_answer,
                    extracted_thinking or None,
                    _done_meta.get("model"),
                    _done_meta.get("input_tokens", 0),
                    _done_meta.get("output_tokens", 0),
                    _done_meta.get("latency_ms", 0),
                    _done_meta.get("tool_rounds", 0),
                    json.dumps(tool_calls_data) if tool_calls_data else None,
                    finish_time,
                ),
            )
            # usage_stats 每日聚合（MySQL only）
            if _DB_TYPE == "mysql" and (_done_meta.get("input_tokens") or _done_meta.get("output_tokens")):
                today = datetime.now(timezone.utc).date().isoformat()
                try:
                    await db.execute(
                        """INSERT INTO usage_stats
                           (user_id, model, stat_date, input_tokens, output_tokens, messages)
                           VALUES (%s, %s, %s, %s, %s, 1)
                           ON DUPLICATE KEY UPDATE
                             input_tokens  = input_tokens  + VALUES(input_tokens),
                             output_tokens = output_tokens + VALUES(output_tokens),
                             messages      = messages + 1""",
                        (
                            current_user_id or 'anonymous',
                            _done_meta.get("model", ""),
                            today,
                            _done_meta.get("input_tokens", 0),
                            _done_meta.get("output_tokens", 0),
                        ),
                    )
                except Exception:
                    pass
            await db.execute(
                "UPDATE app_sessions SET updated_at=? WHERE id=?",
                (finish_time, session_id),
            )
            await db.commit()
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
