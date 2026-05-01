from __future__ import annotations

import logging
from contextlib import asynccontextmanager

# ── 日志系统：最先初始化，保证所有模块的 logger 都生效 ──
from .core.logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .core.config import get_settings
from .db.database import init_db, close_db, get_db
from .llm.client import LLMClient
from .tools.registry import ToolRegistry
from .ws.manager import ws_manager
from .engine.executor import WorkflowEngine

from .api.workflows import router as workflows_router
from .api.executions import router as executions_router
from .api.templates import router as templates_router
from .api.tools import router as tools_router
from .api.models import router as models_router
from .api.secrets import router as secrets_router
from .api.skills import router as skills_router
from .api.prompts import router as prompts_router
from .api.mcp import router as mcp_router
from .api.permissions import router as permissions_router
from .api.knowledge import router as knowledge_router
from .api.settings import router as settings_router
from .api.chat import router as chat_router
from .api.apps import router as apps_router
from .api.diagram import router as diagram_router
from .api.auth import router as auth_router
from .api.memories import router as memories_router
from .api.tasks import router as tasks_router
from .api.approvals import router as approvals_router
from .api.agent_runs import router as agent_runs_router
from .api.analytics import router as analytics_router
from .api.schedules import router as schedules_router
from .api.evals import router as evals_router


async def _seed_model_configs(settings) -> None:
    """Seed model_configs table from .env settings (upsert: always sync latest config)."""
    import os
    import json
    from datetime import datetime, timezone
    from .db.database import get_db

    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()

    models_to_seed = []

    # Main LLM
    if settings.llm_default_model:
        models_to_seed.append({
            "id": "model_main_llm",
            "provider": settings.llm_provider,
            "name": f"主模型 ({settings.llm_default_model})",
            "model_id": settings.llm_default_model,
            "api_base": settings.llm_base_url,
            "api_key_ref": settings.llm_api_key,
            "is_default": 1,
            "max_tokens": 4096,
            "config": json.dumps({
                "role": "main",
                "custCode": settings.llm_custcode,
                "componentCode": settings.llm_componentcode,
            }),
        })

    # L1 LLM
    if settings.l1_llm_model:
        models_to_seed.append({
            "id": "model_l1_llm",
            "provider": settings.llm_provider,
            "name": f"轻量模型 ({settings.l1_llm_model})",
            "model_id": settings.l1_llm_model,
            "api_base": settings.l1_llm_base_url or settings.llm_base_url,
            "api_key_ref": settings.l1_llm_api_key or settings.llm_api_key,
            "is_default": 0,
            "max_tokens": 2048,
            "config": json.dumps({
                "role": "l1",
                "custCode": settings.l1_llm_custcode or settings.llm_custcode,
                "componentCode": settings.l1_llm_componentcode or settings.llm_componentcode,
            }),
        })

    # Multimodal (MMP)
    mmp_model = os.getenv("MMP_MODEL", "")
    if mmp_model:
        models_to_seed.append({
            "id": "model_mmp",
            "provider": settings.llm_provider,
            "name": f"多模态 ({mmp_model})",
            "model_id": mmp_model,
            "api_base": os.getenv("MMP_BASE_URL", settings.llm_base_url),
            "api_key_ref": os.getenv("MMP_API_KEY", settings.llm_api_key),
            "is_default": 0,
            "max_tokens": 4096,
            "config": json.dumps({
                "role": "multimodal",
                "custCode": os.getenv("MMP_CUSTCODE", settings.llm_custcode),
                "componentCode": os.getenv("MMP_COMPONENTCODE", ""),
            }),
        })

    # Embedding
    if settings.embedding_model:
        models_to_seed.append({
            "id": "model_embedding",
            "provider": settings.llm_provider,
            "name": f"Embedding ({settings.embedding_model})",
            "model_id": settings.embedding_model,
            "api_base": settings.embedding_base_url or settings.llm_base_url,
            "api_key_ref": settings.embedding_api_key or settings.llm_api_key,
            "is_default": 0,
            "max_tokens": 0,
            "config": json.dumps({
                "role": "embedding",
                "custCode": settings.embedding_custcode or settings.llm_custcode,
                "componentCode": settings.embedding_componentcode or settings.llm_componentcode,
                "dim": settings.embedding_dim,
            }),
        })

    for m in models_to_seed:
        await db.execute(
            """INSERT OR REPLACE INTO model_configs
               (id, provider, name, model_id, api_base, api_key_ref, is_default, max_tokens, config, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM model_configs WHERE id = ?), ?), ?)""",
            (m["id"], m["provider"], m["name"], m["model_id"],
             m["api_base"], m["api_key_ref"], m["is_default"],
             m["max_tokens"], m["config"], m["id"], now, now),
        )
    await db.commit()

    # AIPro: auto-discover models from /v1/models
    if settings.aipro_base_url and settings.aipro_api_key:
        await _discover_aipro_models(db, settings, now)


async def _discover_aipro_models(db, settings, now: str) -> None:
    """Fetch model list from aipro and upsert to model_configs."""
    import httpx, json
    base = settings.aipro_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {settings.aipro_api_key}"},
            )
        if resp.status_code != 200:
            logger.warning(f"AIPro /v1/models returned {resp.status_code}")
            return
        data = resp.json()
    except Exception as e:
        logger.warning(f"AIPro model discovery failed: {e}")
        return

    _MODEL_MAX_TOKENS: dict[str, int] = {
        "claude-opus-4-6": 32000,
        "claude-sonnet-4-6": 16000,
        "claude-haiku-3-5": 8192,
        "claude-opus-4-6-thinking": 32000,
        "claude-sonnet-4-6-thinking": 16000,
        "gpt-4o": 16384,
        "gpt-4o-mini": 16384,
        "gpt-4-turbo": 4096,
        "gpt-4": 8192,
        "o1": 32768,
        "o3": 100000,
        "gemini-2.5-pro": 65536,
        "gemini-2.0-flash": 8192,
    }

    def _get_max_tokens(model_id: str) -> int:
        for prefix, tokens in _MODEL_MAX_TOKENS.items():
            if model_id.startswith(prefix) or prefix in model_id:
                return tokens
        return 8192

    models = data.get("data", [])
    default_model = settings.aipro_default_model
    count = 0
    for m in models:
        mid = m.get("id", "")
        if not mid:
            continue
        db_id = f"aipro_{mid.replace('/', '_').replace('.', '_').replace('-', '_')}"
        is_default = 1 if mid == default_model else 0
        max_tok = m.get("max_tokens") or _get_max_tokens(mid)
        await db.execute(
            """INSERT OR REPLACE INTO model_configs
               (id, provider, name, model_id, api_base, api_key_ref, is_default, max_tokens, config, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM model_configs WHERE id = ?), ?), ?)""",
            (db_id, "openai", f"[AIPro] {mid}", mid,
             f"{base}", settings.aipro_api_key,
             is_default, max_tok, json.dumps({"role": "aipro"}), db_id, now, now),
        )
        count += 1
    await db.commit()
    logger.info(f"AIPro: registered {count} models from {base}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Database
    await init_db(settings.db_path)

    # Seed model configs from .env
    await _seed_model_configs(settings)

    # Seed built-in skills, prompts
    from .db.seed_data import seed_builtin_data
    await seed_builtin_data(await get_db())

    # LLM Client
    llm_client = LLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        provider=settings.llm_provider,
        custcode=settings.llm_custcode,
        componentcode=settings.llm_componentcode,
    )
    app.state.llm_client = llm_client

    # Tool Registry
    tool_registry = ToolRegistry()
    tool_registry.register_defaults()
    app.state.tool_registry = tool_registry

    # Workflow Engine
    engine = WorkflowEngine(llm=llm_client, tools=tool_registry, ws=ws_manager)
    app.state.engine = engine

    # WebSocket Manager
    app.state.ws_manager = ws_manager

    yield

    await close_db()


_OUTPUTS_DIR = Path("static/outputs")
_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Agent Flow API",
    version="0.1.0",
    description="Agent orchestration workflow engine",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/outputs", StaticFiles(directory=str(_OUTPUTS_DIR)), name="outputs")

# REST API routers
app.include_router(auth_router)
app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(templates_router)
app.include_router(tools_router)
app.include_router(models_router)
app.include_router(secrets_router)
app.include_router(skills_router)
app.include_router(prompts_router)
app.include_router(mcp_router)
app.include_router(permissions_router)
app.include_router(knowledge_router)
app.include_router(settings_router)
app.include_router(chat_router)
app.include_router(apps_router)
app.include_router(diagram_router)
app.include_router(memories_router)
app.include_router(tasks_router)
app.include_router(approvals_router)
app.include_router(agent_runs_router)
app.include_router(analytics_router)
app.include_router(schedules_router)
app.include_router(evals_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.websocket("/ws/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    await ws_manager.connect(websocket, execution_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, execution_id)


@app.websocket("/ws")
async def ws_global(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
