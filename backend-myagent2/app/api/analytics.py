"""用量统计查询接口，从 usage_stats 表聚合数据（MySQL only）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from ..db.database import get_db, _db_type as _DB_TYPE

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/usage")
async def get_usage(
    days: int = Query(default=30, ge=1, le=365),
    user_id: str = "",
    model: str = "",
):
    """
    返回最近 N 天每日 token 用量。
    SQLite 环境返回空数据（usage_stats 仅在 MySQL 中写入）。
    """
    if _DB_TYPE != "mysql":
        return {"items": [], "summary": {"total_input": 0, "total_output": 0, "total_messages": 0}}

    db = await get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    conds = ["stat_date >= %s"]
    params: list = [since]
    if user_id:
        conds.append("user_id = %s")
        params.append(user_id)
    if model:
        conds.append("model = %s")
        params.append(model)

    where = " AND ".join(conds)
    cur = await db.execute(
        f"""SELECT stat_date, model,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(messages) AS messages,
                   SUM(tool_calls) AS tool_calls
            FROM usage_stats
            WHERE {where}
            GROUP BY stat_date, model
            ORDER BY stat_date ASC""",
        params,
    )
    rows = await cur.fetchall()
    items = [dict(r) for r in rows]

    total_input = sum(int(r.get("input_tokens") or 0) for r in items)
    total_output = sum(int(r.get("output_tokens") or 0) for r in items)
    total_messages = sum(int(r.get("messages") or 0) for r in items)

    return {
        "items": items,
        "summary": {
            "total_input": total_input,
            "total_output": total_output,
            "total_messages": total_messages,
            "total_tokens": total_input + total_output,
        },
    }


@router.get("/usage/models")
async def get_usage_by_model(days: int = Query(default=30, ge=1, le=365)):
    """按模型分组汇总用量。"""
    if _DB_TYPE != "mysql":
        return {"items": []}

    db = await get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    cur = await db.execute(
        """SELECT model,
                  SUM(input_tokens)  AS input_tokens,
                  SUM(output_tokens) AS output_tokens,
                  SUM(messages)      AS messages,
                  SUM(tool_calls)    AS tool_calls
           FROM usage_stats
           WHERE stat_date >= %s
           GROUP BY model
           ORDER BY SUM(input_tokens + output_tokens) DESC""",
        [since],
    )
    rows = await cur.fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/usage/users")
async def get_usage_by_user(days: int = Query(default=30, ge=1, le=365), limit: int = 20):
    """按用户分组汇总用量（Top N）。"""
    if _DB_TYPE != "mysql":
        return {"items": []}

    db = await get_db()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    cur = await db.execute(
        """SELECT user_id,
                  SUM(input_tokens)  AS input_tokens,
                  SUM(output_tokens) AS output_tokens,
                  SUM(messages)      AS messages
           FROM usage_stats
           WHERE stat_date >= %s
           GROUP BY user_id
           ORDER BY SUM(input_tokens + output_tokens) DESC
           LIMIT %s""",
        [since, limit],
    )
    rows = await cur.fetchall()
    return {"items": [dict(r) for r in rows]}
