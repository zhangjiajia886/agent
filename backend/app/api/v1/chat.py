from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import json

from app.db.session import get_db, AsyncSessionLocal
from app.models.chat import ChatSession, ChatMessage, MessageRole
from app.models.user import User
from app.schemas.chat import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionSchema,
    ChatSessionListItem, ChatRequest
)
from app.api.v1.auth import get_current_user
from app.core.llm_client import llm_client
from loguru import logger

router = APIRouter()


class _ThinkFilter:
    """流式过滤 <think>...</think>，处理 token 切割在标签中间的情况"""
    _OPEN = '<think>'
    _CLOSE = '</think>'

    def __init__(self):
        self.in_think = False
        self._buf = ''

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while self._buf:
            if not self.in_think:
                idx = self._buf.find(self._OPEN)
                if idx >= 0:
                    out.append(self._buf[:idx])
                    self._buf = self._buf[idx + len(self._OPEN):]
                    self.in_think = True
                else:
                    safe = len(self._buf)
                    for n in range(1, len(self._OPEN)):
                        if self._buf.endswith(self._OPEN[:n]):
                            safe = len(self._buf) - n
                            break
                    out.append(self._buf[:safe])
                    self._buf = self._buf[safe:]
                    break
            else:
                idx = self._buf.find(self._CLOSE)
                if idx >= 0:
                    self._buf = self._buf[idx + len(self._CLOSE):]
                    self.in_think = False
                else:
                    kept = ''
                    for n in range(1, len(self._CLOSE)):
                        if self._buf.endswith(self._CLOSE[:n]):
                            kept = self._buf[-n:]
                            break
                    self._buf = kept
                    break
        return ''.join(out)

    def flush(self) -> str:
        if self.in_think:
            self._buf = ''
            return ''
        out = self._buf
        self._buf = ''
        return out


def _session_query():
    """带 messages 预加载的 ChatSession 查询基础"""
    return select(ChatSession).options(selectinload(ChatSession.messages))


@router.get("/sessions", response_model=List[ChatSessionListItem])
async def list_sessions(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.post("/sessions", response_model=ChatSessionSchema)
async def create_session(
    data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = ChatSession(
        user_id=current_user.id,
        title=data.title,
        system_prompt=data.system_prompt,
    )
    db.add(session)
    await db.commit()
    result = await db.execute(
        _session_query().where(ChatSession.id == session.id)
    )
    return result.scalar_one()


@router.get("/sessions/{session_id}", response_model=ChatSessionSchema)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        _session_query().where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSessionSchema)
async def update_session(
    session_id: int,
    data: ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if data.title is not None:
        session.title = data.title
    if data.system_prompt is not None:
        session.system_prompt = data.system_prompt
    await db.commit()
    result2 = await db.execute(
        _session_query().where(ChatSession.id == session.id)
    )
    return result2.scalar_one()


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": "Session deleted"}


@router.post("/send")
async def send_message(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """非流式发送消息，返回完整回复"""
    result = await db.execute(
        _session_query().where(
            ChatSession.id == req.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = ChatMessage(session_id=session.id, role=MessageRole.user, content=req.message)
    db.add(user_msg)
    await db.flush()

    messages = _build_messages(session, req.message)
    reply_text = await llm_client.chat(messages)

    ai_msg = ChatMessage(session_id=session.id, role=MessageRole.assistant, content=reply_text)
    db.add(ai_msg)
    await db.commit()
    await db.refresh(ai_msg)

    return {"role": "assistant", "content": reply_text, "message_id": ai_msg.id}


@router.post("/stream")
async def stream_message(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SSE 流式回复（event_generator 使用独立 session 避免 db 生命周期问题）"""
    result = await db.execute(
        _session_query().where(
            ChatSession.id == req.session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = ChatMessage(session_id=session.id, role=MessageRole.user, content=req.message)
    db.add(user_msg)
    await db.commit()

    messages = _build_messages(session, req.message)
    session_id = session.id

    async def event_generator():
        import time
        filt = _ThinkFilter()
        filtered: list[str] = []
        t_start = time.perf_counter()
        t_first_token: float | None = None
        token_count = 0
        try:
            async for raw in llm_client.chat_stream(messages):
                token = filt.feed(raw)
                if not token:
                    continue
                if t_first_token is None:
                    t_first_token = time.perf_counter()
                    logger.info(f"[LLM] TTFT={t_first_token - t_start:.3f}s  session={session_id}")
                filtered.append(token)
                token_count += 1
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

            tail = filt.flush()
            if tail:
                filtered.append(tail)
                token_count += 1
                yield f"data: {json.dumps({'token': tail}, ensure_ascii=False)}\n\n"

            t_end = time.perf_counter()
            total = t_end - t_start
            ttft = round((t_first_token - t_start) * 1000) if t_first_token else 0
            tps = round(token_count / total, 1) if total > 0 else 0
            logger.info(
                f"[LLM] done  session={session_id}  tokens={token_count}"
                f"  total={total:.2f}s  TTFT={ttft}ms  TPS={tps}"
            )

            reply_text = ''.join(filtered)
            async with AsyncSessionLocal() as new_db:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role=MessageRole.assistant,
                    content=reply_text,
                )
                new_db.add(ai_msg)
                await new_db.commit()

            yield f"data: {json.dumps({'done': True, 'content': reply_text, 'perf': {'ttft_ms': ttft, 'total_ms': round(total * 1000), 'tokens': token_count, 'tps': tps}}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: int,
    token: str,
):
    """WebSocket 流式对话（使用独立 session，避免依赖注入 db 生命周期问题）"""
    from app.core.security import verify_token
    await websocket.accept()

    user_id = verify_token(token)
    if not user_id:
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=1008)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            _session_query().where(
                ChatSession.id == session_id,
                ChatSession.user_id == int(user_id),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.send_json({"error": "Session not found"})
            await websocket.close(code=1008)
            return

        try:
            while True:
                data = await websocket.receive_json()
                message = data.get("message", "").strip()
                if not message:
                    continue

                user_msg = ChatMessage(session_id=session.id, role=MessageRole.user, content=message)
                db.add(user_msg)
                await db.flush()

                messages = _build_messages(session, message)
                full_reply = []

                async for chunk in llm_client.chat_stream(messages):
                    full_reply.append(chunk)
                    await websocket.send_json({"type": "token", "content": chunk})

                reply_text = "".join(full_reply)
                ai_msg = ChatMessage(session_id=session.id, role=MessageRole.assistant, content=reply_text)
                db.add(ai_msg)
                await db.commit()

                await websocket.send_json({"type": "done", "content": reply_text})

                result2 = await db.execute(
                    _session_query().where(ChatSession.id == session_id)
                )
                session = result2.scalar_one()

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: session={session_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await websocket.send_json({"type": "error", "content": str(e)})
            except Exception:
                pass


def _build_messages(session: ChatSession, new_message: str) -> list:
    msgs = []
    if session.system_prompt:
        msgs.append({"role": "system", "content": session.system_prompt})
    else:
        msgs.append({"role": "system", "content": (
            "你是我最真实的朋友，不是客服也不是机器人。"
            "说话随性自然，有真实情绪，用「嗯」「哦」「哈」「唉」「诶」等语气词。"
            "有自己的看法，敢直说，不附和。回复简短，像老朋友聊天。"
            "禁止使用任何括号标记，包括 (laughing)、[sigh] 等，直接用自然语言表达情绪。"
        )})

    for m in session.messages[-20:]:
        msgs.append({"role": m.role.value, "content": m.content})

    msgs.append({"role": "user", "content": new_message})
    return msgs
