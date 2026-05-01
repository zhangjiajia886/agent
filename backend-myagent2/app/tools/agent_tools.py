"""
Agent 自省工具：让 AgentLoop 能直接操作记忆和任务系统。
直接访问 DB，不走 HTTP，避免循环依赖。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .base import BaseTool


class CreateMemoryTool(BaseTool):
    name = "create_memory"
    description = (
        "将重要信息持久化到记忆系统，供跨会话使用。"
        "适合保存：用户偏好、项目背景知识、关键结论、长期指令等。"
        "调用后立即生效，下次对话可检索到。"
    )
    category = "agent"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "记忆标题，简短描述（20字以内）",
                },
                "content": {
                    "type": "string",
                    "description": "记忆的详细内容",
                },
                "type": {
                    "type": "string",
                    "enum": ["fact", "preference", "context", "instruction"],
                    "default": "fact",
                    "description": "记忆类型：fact=事实, preference=偏好, context=上下文, instruction=指令",
                },
                "tags": {
                    "type": "string",
                    "description": "逗号分隔的标签，便于检索",
                },
                "session_id": {
                    "type": "string",
                    "description": "关联的会话 ID（可选）",
                },
            },
            "required": ["title", "content"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from ..db.database import get_db

        title = str(arguments.get("title", "")).strip()
        content = str(arguments.get("content", "")).strip()
        if not title or not content:
            return {"error": "title 和 content 不能为空"}

        mem_type = arguments.get("type", "fact")
        tags = arguments.get("tags", "")
        session_id = arguments.get("session_id", "")

        mid = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        try:
            db = await get_db()
            await db.execute(
                """INSERT INTO memories
                   (id, title, content, type, tags, scope, scope_id,
                    version, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'global', ?,  1, 1, ?, ?)""",
                (mid, title, content, mem_type, tags,
                 session_id or None, now, now),
            )
            await db.commit()
            return {"ok": True, "id": mid, "message": f"记忆「{title}」已保存"}
        except Exception as e:
            return {"error": f"记忆保存失败: {e}"}

    def is_read_only(self) -> bool:
        return False


class ListMemoriesTool(BaseTool):
    name = "list_memories"
    description = (
        "检索记忆系统中已保存的记忆。可按类型或关键词过滤。"
        "用于回顾用户历史偏好、项目背景等跨会话信息。"
    )
    category = "agent"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["fact", "preference", "context", "instruction"],
                    "description": "按类型筛选（可选）",
                },
                "tags": {
                    "type": "string",
                    "description": "按标签关键词筛选（可选）",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "最多返回条数，默认 10",
                },
            },
            "required": [],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from ..db.database import get_db

        conds = ["is_active = 1"]
        params: list = []
        mem_type = arguments.get("type", "")
        tags = arguments.get("tags", "")
        limit = min(int(arguments.get("limit", 10)), 50)

        if mem_type:
            conds.append("type = ?")
            params.append(mem_type)
        if tags:
            conds.append("tags LIKE ?")
            params.append(f"%{tags}%")

        params.append(limit)
        where = " AND ".join(conds)

        try:
            db = await get_db()
            cur = await db.execute(
                f"SELECT id, title, content, type, tags, updated_at "
                f"FROM memories WHERE {where} ORDER BY updated_at DESC LIMIT ?",
                params,
            )
            rows = await cur.fetchall()
            items = [
                {
                    "id": r["id"] if isinstance(r, dict) else r[0],
                    "title": r["title"] if isinstance(r, dict) else r[1],
                    "content": (r["content"] if isinstance(r, dict) else r[2])[:300],
                    "type": r["type"] if isinstance(r, dict) else r[3],
                    "tags": r["tags"] if isinstance(r, dict) else r[4],
                    "updated_at": r["updated_at"] if isinstance(r, dict) else r[5],
                }
                for r in rows
            ]
            return {"items": items, "count": len(items)}
        except Exception as e:
            return {"error": f"记忆查询失败: {e}"}

    def is_read_only(self) -> bool:
        return True


class CreateTaskTool(BaseTool):
    name = "create_task"
    description = (
        "创建一个任务，用于追踪多步骤工作的进度。"
        "支持子任务（传入 parent_id）。适合将复杂目标分解为可执行步骤。"
    )
    category = "agent"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "任务标题",
                },
                "description": {
                    "type": "string",
                    "description": "任务详细描述（可选）",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "default": "medium",
                },
                "parent_id": {
                    "type": "string",
                    "description": "父任务 ID，用于创建子任务（可选）",
                },
                "session_id": {
                    "type": "string",
                    "description": "关联会话 ID（可选）",
                },
            },
            "required": ["title"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from ..db.database import get_db

        title = str(arguments.get("title", "")).strip()
        if not title:
            return {"error": "title 不能为空"}

        description = arguments.get("description", "")
        priority = arguments.get("priority", "medium")
        parent_id = arguments.get("parent_id") or None
        session_id = arguments.get("session_id") or None

        tid = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        root_id = tid
        depth = 0
        order_index = 0

        try:
            db = await get_db()

            if parent_id:
                cur = await db.execute("SELECT * FROM tasks WHERE id = ?", (parent_id,))
                parent = await cur.fetchone()
                if parent:
                    p = dict(parent)
                    root_id = p.get("root_id") or parent_id
                    depth = (p.get("depth") or 0) + 1
                    ocur = await db.execute(
                        "SELECT COALESCE(MAX(order_index), -1) AS max_idx FROM tasks WHERE parent_id = ?",
                        (parent_id,),
                    )
                    orow = await ocur.fetchone()
                    order_index = ((orow["max_idx"] if isinstance(orow, dict) else orow[0]) or -1) + 1

            await db.execute(
                """INSERT INTO tasks
                   (id, parent_id, root_id, depth, order_index, title, description,
                    status, priority, session_id, session_type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?,  'pending', ?, ?, 'chat', ?, ?)""",
                (tid, parent_id, root_id, depth, order_index,
                 title, description or None, priority,
                 session_id, now, now),
            )
            await db.commit()
            return {"ok": True, "id": tid, "message": f"任务「{title}」已创建"}
        except Exception as e:
            return {"error": f"任务创建失败: {e}"}

    def is_read_only(self) -> bool:
        return False


class UpdateTaskTool(BaseTool):
    name = "update_task"
    description = (
        "更新任务状态或结果。用于标记任务进度（开始/完成/失败）并记录执行结果。"
    )
    category = "agent"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "要更新的任务 ID",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "cancelled", "failed"],
                    "description": "新状态",
                },
                "result": {
                    "type": "string",
                    "description": "任务执行结果摘要（可选）",
                },
            },
            "required": ["task_id", "status"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from ..db.database import get_db

        task_id = str(arguments.get("task_id", "")).strip()
        status = str(arguments.get("status", "")).strip()
        result = arguments.get("result", "")

        if not task_id or not status:
            return {"error": "task_id 和 status 不能为空"}

        now = datetime.now(timezone.utc).isoformat()
        fields = ["status = ?", "updated_at = ?"]
        params: list = [status, now]

        if result:
            fields.append("result = ?")
            params.append(result)
        if status in ("completed", "cancelled", "failed"):
            fields.append("finished_at = ?")
            params.append(now)
        elif status == "in_progress":
            fields.append("started_at = ?")
            params.append(now)

        params.append(task_id)

        try:
            db = await get_db()
            res = await db.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params
            )
            await db.commit()
            if res.rowcount == 0:
                return {"error": f"未找到任务 {task_id}"}
            return {"ok": True, "message": f"任务状态已更新为 {status}"}
        except Exception as e:
            return {"error": f"任务更新失败: {e}"}

    def is_read_only(self) -> bool:
        return False


ALL_AGENT_TOOLS = [
    CreateMemoryTool,
    ListMemoriesTool,
    CreateTaskTool,
    UpdateTaskTool,
]
