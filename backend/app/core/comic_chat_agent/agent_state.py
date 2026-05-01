"""
AgentStateStore —— P9 Redis 运行时状态层。

Redis 只保存可过期、可重建的临时运行状态；DB 仍是权威状态。
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.config import settings


_TASK_LOCK_TTL_SECONDS = 60 * 60
_APPROVAL_TTL_SECONDS = 5 * 60
_BUDGET_TTL_SECONDS = 24 * 60 * 60
_TOOL_HEALTH_TTL_SECONDS = 60

_redis_client: redis.Redis | None = None


async def get_agent_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
    return _redis_client


class AgentStateStore:
    def task_lock_key(self, task_uid: str) -> str:
        return f"agent:task:{task_uid}:lock"

    def approval_key(self, task_uid: str) -> str:
        return f"agent:task:{task_uid}:approval"

    def budget_key(self, task_uid: str) -> str:
        return f"agent:task:{task_uid}:budget"

    def tool_health_key(self, tool_name: str) -> str:
        return f"agent:tool:{tool_name}:health"

    async def acquire_task_lock(self, task_uid: str, owner: str, ttl_seconds: int = _TASK_LOCK_TTL_SECONDS) -> bool:
        client = await get_agent_redis()
        return bool(await client.set(self.task_lock_key(task_uid), owner, ex=ttl_seconds, nx=True))

    async def renew_task_lock(self, task_uid: str, ttl_seconds: int = _TASK_LOCK_TTL_SECONDS) -> bool:
        client = await get_agent_redis()
        return bool(await client.expire(self.task_lock_key(task_uid), ttl_seconds))

    async def release_task_lock(self, task_uid: str) -> None:
        client = await get_agent_redis()
        await client.delete(self.task_lock_key(task_uid))

    async def set_approval_waiting(self, task_uid: str, payload: dict[str, Any], ttl_seconds: int = _APPROVAL_TTL_SECONDS) -> None:
        client = await get_agent_redis()
        await client.set(self.approval_key(task_uid), json.dumps(payload, ensure_ascii=False), ex=ttl_seconds)

    async def clear_approval(self, task_uid: str) -> None:
        client = await get_agent_redis()
        await client.delete(self.approval_key(task_uid))

    async def increment_budget_counter(self, task_uid: str, field: str, amount: int = 1, ttl_seconds: int = _BUDGET_TTL_SECONDS) -> int:
        client = await get_agent_redis()
        key = self.budget_key(task_uid)
        value = await client.hincrby(key, field, amount)
        await client.expire(key, ttl_seconds)
        return int(value)

    async def clear_budget_counter(self, task_uid: str) -> None:
        client = await get_agent_redis()
        await client.delete(self.budget_key(task_uid))

    async def set_tool_health(self, tool_name: str, payload: dict[str, Any], ttl_seconds: int = _TOOL_HEALTH_TTL_SECONDS) -> None:
        client = await get_agent_redis()
        await client.set(self.tool_health_key(tool_name), json.dumps(payload, ensure_ascii=False), ex=ttl_seconds)

    async def get_tool_health(self, tool_name: str) -> dict[str, Any] | None:
        client = await get_agent_redis()
        raw = await client.get(self.tool_health_key(tool_name))
        return json.loads(raw) if raw else None
