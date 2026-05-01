"""
CheckpointManager — 工作流断点持久化与恢复（SQLAlchemy ORM 版）。
来源: backend-myagent2/app/engine/checkpoint.py，改用 SQLAlchemy 替代 aiosqlite。
"""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.workflow import ExecutionCheckpoint

if TYPE_CHECKING:
    from .context import ExecutionContext


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
            state = {
                "variables": _serialize_variables(ctx.variables),
                "outputs": ctx.get_outputs(),
                "node_results": ctx.node_results,
            }

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ExecutionCheckpoint).where(
                        ExecutionCheckpoint.execution_id == self.execution_id
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    existing.node_id = node_id
                    existing.state = state
                    existing.completed_nodes = list(completed_nodes)
                else:
                    ckpt = ExecutionCheckpoint(
                        id=f"ckpt_{uuid.uuid4().hex[:12]}",
                        execution_id=self.execution_id,
                        node_id=node_id,
                        state=state,
                        completed_nodes=list(completed_nodes),
                    )
                    db.add(ckpt)

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
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ExecutionCheckpoint)
                    .where(ExecutionCheckpoint.execution_id == self.execution_id)
                    .order_by(ExecutionCheckpoint.checkpoint_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if not row:
                    return None

                completed = set(row.completed_nodes or [])
                logger.info(
                    f"[CKPT LOAD] exec={self.execution_id} "
                    f"node={row.node_id} completed={len(completed)}"
                )
                return {
                    "id": row.id,
                    "node_id": row.node_id,
                    "state": row.state or {},
                    "completed_nodes": completed,
                    "checkpoint_at": str(row.checkpoint_at),
                }
        except Exception as e:
            logger.warning(f"[CKPT LOAD FAILED] exec={self.execution_id}: {e}")
            return None

    async def delete(self) -> None:
        """清除断点（执行成功后可选调用）。"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ExecutionCheckpoint).where(
                        ExecutionCheckpoint.execution_id == self.execution_id
                    )
                )
                for row in result.scalars():
                    await db.delete(row)
                await db.commit()
        except Exception as e:
            logger.warning(f"[CKPT DELETE FAILED] exec={self.execution_id}: {e}")

    async def get_info(self) -> dict | None:
        """返回断点摘要，不含完整 state，用于前端进度展示。"""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(ExecutionCheckpoint)
                    .where(ExecutionCheckpoint.execution_id == self.execution_id)
                    .order_by(ExecutionCheckpoint.checkpoint_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if not row:
                    return None
                completed = row.completed_nodes or []
                return {
                    "has_checkpoint": True,
                    "checkpoint_id": row.id,
                    "last_node_id": row.node_id,
                    "completed_nodes": completed,
                    "completed_count": len(completed),
                    "checkpoint_at": str(row.checkpoint_at),
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
