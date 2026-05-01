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
from ..agent.loop import _pending_confirms, _confirm_actions


def _extract_thinking(full_content: str) -> tuple[str, str]:
    """从累积的 delta 内容中分离 thinking 和 clean answer。"""
    for tag in ('thinking', 'think'):
        m = re.match(rf'^<{tag}>([\s\S]*?)</{tag}>\s*([\s\S]*)$', full_content.strip())
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return '', full_content

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _session_row(r) -> dict:
    d = dict(r)
    return d


def _message_row(r) -> dict:
    d = dict(r)
    # 将 metadata JSON 字段反序列化
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            d["metadata"] = {}
    # 将 tool_calls JSON 字段反序列化
    if "tool_calls" in d and isinstance(d["tool_calls"], str):
        try:
            d["tool_calls"] = json.loads(d["tool_calls"])
        except Exception:
            d["tool_calls"] = None
    return d


# ── Pydantic Models ──

class SessionCreate(BaseModel):
    title: str = ""
    model: str = ""
    system_prompt: str = ""


class SessionUpdate(BaseModel):
    title: str | None = None
    model: str | None = None
    system_prompt: str | None = None


class MessageSend(BaseModel):
    content: str
    model: str | None = None


# ── Session CRUD ──

@router.get("/sessions")
async def list_sessions():
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM chat_sessions ORDER BY updated_at DESC"
    )
    items = await rows.fetchall()
    return {"items": [_session_row(r) for r in items]}


@router.post("/sessions")
async def create_session(
    body: SessionCreate,
    current_user: dict | None = Depends(get_current_user_optional),
):
    db = await get_db()
    sid = f"chat_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    title = body.title or "新对话"
    _user_id = current_user["sub"] if current_user else None
    await db.execute(
        """INSERT INTO chat_sessions
           (id, title, model, system_prompt, user_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sid, title, body.model, body.system_prompt, _user_id, now, now),
    )
    await db.commit()
    return {"id": sid, "title": title, "created_at": now}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    db = await get_db()
    row = await db.execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    )
    session = await row.fetchone()
    if not session:
        raise HTTPException(404, "Session not found")

    msgs = await db.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    )
    messages = [_message_row(m) for m in await msgs.fetchall()]
    result = _session_row(session)
    result["messages"] = messages
    return result


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, body: SessionUpdate):
    db = await get_db()
    fields, params = [], []
    if body.title is not None:
        fields.append("title = ?"); params.append(body.title)
    if body.model is not None:
        fields.append("model = ?"); params.append(body.model)
    if body.system_prompt is not None:
        fields.append("system_prompt = ?"); params.append(body.system_prompt)
    if fields:
        fields.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(session_id)
        await db.execute(
            f"UPDATE chat_sessions SET {', '.join(fields)} WHERE id = ?", params
        )
        await db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    db = await get_db()
    await db.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    await db.commit()
    return {"ok": True}


# ── Send Message (Streaming) ──

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: MessageSend,
    request: Request,
    current_user: dict | None = Depends(get_current_user_optional),
):
    _current_user_id = current_user["sub"] if current_user else None
    db = await get_db()
    row = await db.execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    )
    session = await row.fetchone()
    if not session:
        raise HTTPException(404, "Session not found")

    # 保存用户消息
    user_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO chat_messages (id, session_id, role, content, created_at)
           VALUES (?, ?, 'user', ?, ?)""",
        (user_msg_id, session_id, body.content, now),
    )
    await db.commit()

    # 更新会话时间 & 自动标题
    session_dict = _session_row(session)
    if session_dict["title"] == "新对话":
        short_title = body.content[:30].replace("\n", " ")
        await db.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
            (short_title, now, session_id),
        )
    else:
        await db.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
    await db.commit()

    # 加载 Agent Loop（延迟导入避免循环依赖）
    from ..agent.loop import AgentLoop

    agent = AgentLoop(
        llm=request.app.state.llm_client,
        tools=request.app.state.tool_registry,
    )

    async def event_stream():
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        full_content = ""
        tool_calls_data = []
        try:
            async for event in agent.run(
                session_id=session_id,
                user_content=body.content,
                model_override=body.model or session_dict.get("model", ""),
                system_prompt_override=session_dict.get("system_prompt", ""),
            ):
                event_type = event.get("type", "")

                if event_type == "delta":
                    full_content += event.get("content", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "tool_start":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "tool_confirm_request":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "tool_result":
                    # 保存 tool message
                    tool_msg_id = f"msg_{uuid.uuid4().hex[:12]}"
                    tool_now = datetime.now(timezone.utc).isoformat()
                    await db.execute(
                        """INSERT INTO chat_messages
                           (id, session_id, role, content, tool_call_id, name, created_at)
                           VALUES (?, ?, 'tool', ?, ?, ?, ?)""",
                        (tool_msg_id, session_id,
                         json.dumps(event.get("result", {})),
                         event.get("tool_call_id", ""),
                         event.get("name", ""),
                         tool_now),
                    )
                    await db.commit()
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "tool_calls":
                    tool_calls_data = event.get("tool_calls", [])
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "done":
                    meta = event.get("metadata", {})
                    done_now = datetime.now(timezone.utc).isoformat()
                    # 从累积的 full_content 提取 thinking（<think> 标签嵌在 delta 流中）
                    extracted_thinking, clean_answer = _extract_thinking(full_content)
                    await db.execute(
                        """INSERT INTO chat_messages
                           (id, session_id, role, content, thinking_content,
                            model, input_tokens, output_tokens, latency_ms, tool_rounds,
                            tool_calls, metadata, created_at)
                           VALUES (?, ?, 'assistant', ?, ?,  ?, ?, ?, ?, ?,  ?, ?, ?)""",
                        (
                            assistant_msg_id, session_id,
                            clean_answer,
                            extracted_thinking or None,
                            meta.get("model"),
                            meta.get("input_tokens", 0),
                            meta.get("output_tokens", 0),
                            meta.get("latency_ms", 0),
                            meta.get("tool_rounds", 0),
                            json.dumps(tool_calls_data) if tool_calls_data else None,
                            json.dumps(meta),
                            done_now,
                        ),
                    )
                    # usage_stats 每日聚合（MySQL only）
                    if _DB_TYPE == "mysql" and (meta.get("input_tokens") or meta.get("output_tokens")):
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
                                    _current_user_id or 'anonymous',
                                    meta.get("model", ""),
                                    today,
                                    meta.get("input_tokens", 0),
                                    meta.get("output_tokens", 0),
                                ),
                            )
                            await db.commit()
                        except Exception as _ue:
                            pass  # 统计失败不影响主流程
                    await db.commit()
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                elif event_type == "error":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Multi-Agent 端点 ──────────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    name: str
    system_prompt: str = ""
    model: str = ""
    allowed_tools: list[str] | None = None
    input_var: str = ""
    output_var: str = ""
    type: str = "llm"


class MultiAgentBody(BaseModel):
    mode: str = "sequential"          # sequential | parallel | supervisor
    user_content: str
    agents: list[AgentConfig]
    execution_id: str = ""            # 可选，关联工作流执行 ID


@router.post("/sessions/{session_id}/multi-agent")
async def multi_agent_chat(
    session_id: str,
    body: MultiAgentBody,
    request: Request,
):
    """流式 Multi-Agent 对话。每个 Agent 事件附加 agent_name 字段。"""
    db = await get_db()
    row = await db.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,))
    if not await row.fetchone():
        raise HTTPException(404, "Session not found")

    from ..agent.orchestrator import MultiAgentOrchestrator

    orchestrator = MultiAgentOrchestrator(
        llm=request.app.state.llm_client,
        tools=request.app.state.tool_registry,
    )
    exec_id = body.execution_id or f"maexec_{uuid.uuid4().hex[:12]}"
    agents_list = [
        {**a.model_dump(), "_index": idx}
        for idx, a in enumerate(body.agents)
    ]

    async def event_stream():
        try:
            async for event in orchestrator.run(
                execution_id=exec_id,
                session_id=session_id,
                mode=body.mode,
                agents=agents_list,
                user_content=body.user_content,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
        finally:
            yield "data: {\"type\":\"stream_end\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Human-in-the-loop 确认接口 ──


class ConfirmBody(BaseModel):
    action: str  # "allow" | "skip" | "cancel"


@router.post("/confirm/{tool_call_id}")
async def confirm_tool_call(tool_call_id: str, body: ConfirmBody):
    """前端确认/跳过/取消工具调用，唤醒 loop.py 中等待的 asyncio.Event"""
    evt = _pending_confirms.get(tool_call_id)
    if evt:
        _confirm_actions[tool_call_id] = body.action
        evt.set()
        return {"ok": True}
    return {"ok": False, "reason": "tool_call_id not found or already resolved"}


# ── Helpers ──

def _session_row(r) -> dict:
    d = dict(r)
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            pass
    return d


def _message_row(r) -> dict:
    d = dict(r)
    for k in ("tool_calls", "metadata"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d
