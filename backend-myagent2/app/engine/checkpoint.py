"""CheckpointManager — 工作流断点持久化与恢复。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ExecutionContext

logger = logging.getLogger(__name__)

CHECKPOINT_MAX_AGE_DAYS = 7


class CheckpointManager:
    """
    负责将 ExecutionContext 快照写入 execution_checkpoints 表，
    并在恢复执行时读取最近一条有效快照。
    一个 execution_id 只保留最新一条 checkpoint（upsert 策略）。
    """

    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    async def save(
        self,
        node_id: str,
        ctx: "ExecutionContext",
        completed_nodes: set[str],
    ) -> None:
        """每个 batch 完成后调用；写入失败只记 warning，不中断执行。"""
        try:
            from ..db.database import get_db
            db = await get_db()
            state = json.dumps(
                {
                    "variables": _serialize_variables(ctx.variables),
                    "outputs": ctx.get_outputs(),
                    "node_results": ctx.node_results,
                },
                ensure_ascii=False,
                default=str,
            )
            completed_json = json.dumps(list(completed_nodes))
            now = datetime.now(timezone.utc).isoformat()

            cur = await db.execute(
                "SELECT id FROM execution_checkpoints WHERE execution_id = ?",
                (self.execution_id,),
            )
            row = await cur.fetchone()

            if row:
                ckpt_id = row["id"] if isinstance(row, dict) else row[0]
                await db.execute(
                    """UPDATE execution_checkpoints
                       SET node_id=?, state=?, completed_nodes=?, checkpoint_at=?
                       WHERE id=?""",
                    (node_id, state, completed_json, now, ckpt_id),
                )
            else:
                await db.execute(
                    """INSERT INTO execution_checkpoints
                       (id, execution_id, node_id, state, completed_nodes, checkpoint_at)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        f"ckpt_{uuid.uuid4().hex[:12]}",
                        self.execution_id,
                        node_id,
                        state,
                        completed_json,
                        now,
                    ),
                )
            await db.commit()
            logger.debug(
                f"[CKPT SAVE] exec={self.execution_id} node={node_id} "
                f"completed={len(completed_nodes)}"
            )
        except Exception as e:
            logger.warning(f"[CKPT SAVE FAILED] exec={self.execution_id}: {e}")

    async def load(self) -> dict | None:
        """
        加载最近一条 checkpoint。
        返回 None 表示无有效断点（首次执行或已过期）。
        """
        try:
            from ..db.database import get_db
            db = await get_db()
            cur = await db.execute(
                """SELECT * FROM execution_checkpoints
                   WHERE execution_id = ?
                   ORDER BY checkpoint_at DESC LIMIT 1""",
                (self.execution_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None

            d = dict(row)
            d["state"] = json.loads(d["state"])
            d["completed_nodes"] = set(json.loads(d.get("completed_nodes") or "[]"))
            logger.info(
                f"[CKPT LOAD] exec={self.execution_id} "
                f"node={d['node_id']} completed={len(d['completed_nodes'])}"
            )
            return d
        except Exception as e:
            logger.warning(f"[CKPT LOAD FAILED] exec={self.execution_id}: {e}")
            return None

    async def delete(self) -> None:
        """清除断点（执行成功后可选调用）。"""
        try:
            from ..db.database import get_db
            db = await get_db()
            await db.execute(
                "DELETE FROM execution_checkpoints WHERE execution_id = ?",
                (self.execution_id,),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[CKPT DELETE FAILED] exec={self.execution_id}: {e}")

    async def get_info(self) -> dict | None:
        """返回断点摘要，不含完整 state，用于前端进度展示。"""
        try:
            from ..db.database import get_db
            db = await get_db()
            cur = await db.execute(
                """SELECT id, node_id, completed_nodes, checkpoint_at
                   FROM execution_checkpoints
                   WHERE execution_id = ?
                   ORDER BY checkpoint_at DESC LIMIT 1""",
                (self.execution_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            completed = json.loads(d.get("completed_nodes") or "[]")
            return {
                "has_checkpoint": True,
                "checkpoint_id": d["id"],
                "last_node_id": d["node_id"],
                "completed_nodes": completed,
                "completed_count": len(completed),
                "checkpoint_at": d["checkpoint_at"],
            }
        except Exception:
            return None


def _serialize_variables(variables: dict) -> dict:
    """将不可序列化的变量值截断为字符串，防止 JSON 序列化失败。"""
    result = {}
    for k, v in variables.items():
        try:
            json.dumps(v)
            result[k] = v
        except (TypeError, ValueError):
            result[k] = str(v)[:10240]
    return result
