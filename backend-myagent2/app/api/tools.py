from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..db.database import get_db

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolTestRequest(BaseModel):
    arguments: dict[str, Any] = {}


@router.get("")
async def list_tools(request: Request, category: str = "", search: str = ""):
    registry = request.app.state.tool_registry
    tools = registry.list_all()
    if category:
        tools = [t for t in tools if t["category"] == category]
    if search:
        s = search.lower()
        tools = [t for t in tools if s in t["name"].lower() or s in t.get("description", "").lower()]

    # Attach real usage stats from DB
    try:
        db = await get_db()
        rows = await db.execute(
            """SELECT tool_name,
                      COUNT(*) AS call_count,
                      CAST(AVG(duration_ms) AS INTEGER) AS avg_ms
               FROM tool_usages
               GROUP BY tool_name"""
        )
        stats = {r["tool_name"]: {"call_count": r["call_count"], "avg_ms": r["avg_ms"]}
                 for r in await rows.fetchall()}
    except Exception:
        stats = {}

    for t in tools:
        s = stats.get(t["name"], {})
        t["call_count"] = s.get("call_count", 0)
        t["avg_duration_ms"] = s.get("avg_ms", 0)

    return {"items": tools}


@router.post("/{tool_name}/test")
async def test_tool(tool_name: str, body: ToolTestRequest, request: Request):
    registry = request.app.state.tool_registry
    try:
        result = await registry.execute(tool_name, body.arguments)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        return {"error": str(e)}
