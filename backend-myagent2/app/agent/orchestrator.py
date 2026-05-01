"""Multi-Agent 调度引擎。

支持三种模式：
- sequential: 串行流水线，前一 Agent 的输出作为下一个的输入
- parallel:   并发运行多个 Agent，通过 asyncio.Queue 合并事件流
- supervisor: Supervisor Agent 通过 <route>worker: 任务</route> 动态路由

所有子 Agent 仍是标准 AgentLoop，只是被调度层协调。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Any

from ..db.database import get_db
from ..llm.client import LLMClient
from ..tools.registry import ToolRegistry
from .loop import AgentLoop

logger = logging.getLogger(__name__)

MAX_ROUTE_ROUNDS = 10  # Supervisor 模式最大路由轮次


class MultiAgentOrchestrator:
    """
    无侵入式 Multi-Agent 调度层。
    每个子 Agent 仍是标准 AgentLoop，通过 shared_context 传递数据。
    """

    def __init__(self, llm: LLMClient, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools

    async def run(
        self,
        execution_id: str,
        session_id: str,
        mode: str,
        agents: list[dict],
        user_content: str,
        shared_context: dict | None = None,
    ) -> AsyncIterator[dict]:
        shared_context = shared_context or {}
        shared_lock = asyncio.Lock()

        if mode == "sequential":
            async for event in self._run_sequential(
                execution_id, session_id, agents, user_content, shared_context, shared_lock
            ):
                yield event
        elif mode == "parallel":
            async for event in self._run_parallel(
                execution_id, session_id, agents, user_content, shared_context, shared_lock
            ):
                yield event
        elif mode == "supervisor":
            if len(agents) < 2:
                yield {"type": "error", "message": "supervisor mode requires at least 2 agents"}
                return
            supervisor = agents[0]
            workers = {a["name"]: a for a in agents[1:]}
            async for event in self._run_supervisor(
                execution_id, session_id, supervisor, workers, user_content, shared_context, shared_lock
            ):
                yield event
        else:
            yield {"type": "error", "message": f"unknown mode: {mode}"}

    # ─── Sequential ──────────────────────────────────────────────────────────

    async def _run_sequential(
        self,
        execution_id: str,
        session_id: str,
        agents: list[dict],
        user_content: str,
        shared_context: dict,
        lock: asyncio.Lock,
    ) -> AsyncIterator[dict]:
        current_input = user_content
        for idx, agent_cfg in enumerate(agents):
            run_id = await self._create_run(execution_id, agent_cfg, idx)
            agent_cfg = dict(agent_cfg)
            # 从 shared_context 读取 input_var
            input_var = agent_cfg.get("input_var")
            if input_var and input_var in shared_context:
                current_input = str(shared_context[input_var])

            async for event in self._run_single_agent(
                execution_id, session_id, agent_cfg, run_id, current_input, shared_context, lock
            ):
                yield event

            # 将输出写入 shared_context[output_var]
            output_var = agent_cfg.get("output_var")
            if output_var:
                async with lock:
                    current_input = str(shared_context.get(output_var, ""))

        yield {"type": "multi_agent_done", "execution_id": execution_id, "mode": "sequential"}

    # ─── Parallel ────────────────────────────────────────────────────────────

    async def _run_parallel(
        self,
        execution_id: str,
        session_id: str,
        agents: list[dict],
        user_content: str,
        shared_context: dict,
        lock: asyncio.Lock,
    ) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        async def run_agent(idx: int, agent_cfg: dict):
            run_id = await self._create_run(execution_id, agent_cfg, idx)
            input_var = agent_cfg.get("input_var")
            inp = str(shared_context.get(input_var, user_content)) if input_var else user_content
            try:
                async for event in self._run_single_agent(
                    execution_id, session_id, agent_cfg, run_id, inp, shared_context, lock
                ):
                    await queue.put(event)
            except Exception as e:
                await queue.put({
                    "type": "agent_error",
                    "agent_name": agent_cfg.get("name", f"agent_{idx}"),
                    "run_id": run_id,
                    "message": str(e),
                })
            finally:
                await queue.put(sentinel)

        tasks = [
            asyncio.create_task(run_agent(idx, agent_cfg))
            for idx, agent_cfg in enumerate(agents)
        ]

        done_count = 0
        while done_count < len(agents):
            item = await queue.get()
            if item is sentinel:
                done_count += 1
            else:
                yield item

        await asyncio.gather(*tasks, return_exceptions=True)
        yield {"type": "multi_agent_done", "execution_id": execution_id, "mode": "parallel"}

    # ─── Supervisor ──────────────────────────────────────────────────────────

    async def _run_supervisor(
        self,
        execution_id: str,
        session_id: str,
        supervisor: dict,
        workers: dict[str, dict],
        user_content: str,
        shared_context: dict,
        lock: asyncio.Lock,
    ) -> AsyncIterator[dict]:
        """
        Supervisor 每轮输出中若含 <route>worker_name: 任务</route>，
        则将任务路由给对应 Worker，Worker 结果注入下一轮 Supervisor 的输入。
        """
        run_id = await self._create_run(execution_id, supervisor, 0)
        worker_run_ids: dict[str, str] = {}
        for idx, (name, wcfg) in enumerate(workers.items()):
            worker_run_ids[name] = await self._create_run(execution_id, wcfg, idx + 1)

        loop_agent = AgentLoop(self.llm, self.tools)
        messages: list[dict] = [{"role": "user", "content": user_content}]

        for route_round in range(MAX_ROUTE_ROUNDS):
            # Supervisor 生成一轮回复
            full_output = ""
            async for event in loop_agent.run(
                session_id=f"{session_id}_supervisor",
                user_content=messages[-1]["content"],
                system_prompt_override=supervisor.get("system_prompt", ""),
                model_override=supervisor.get("model", ""),
                allowed_tools=supervisor.get("allowed_tools"),
                history_override=messages[:-1],
            ):
                event["agent_name"] = supervisor.get("name", "supervisor")
                event["run_id"] = run_id
                yield event
                if event.get("type") == "delta":
                    full_output += event.get("content", "")

            # 解析路由指令
            route_match = re.search(r"<route>\s*(\w+):\s*([\s\S]*?)</route>", full_output)
            if not route_match:
                break  # 无路由指令，Supervisor 输出即最终结果

            worker_name = route_match.group(1).strip()
            worker_task = route_match.group(2).strip()

            if worker_name not in workers:
                yield {
                    "type": "agent_error",
                    "agent_name": worker_name,
                    "message": f"Worker '{worker_name}' not found",
                }
                break

            yield {
                "type": "agent_route",
                "from_agent": supervisor.get("name", "supervisor"),
                "to_agent": worker_name,
                "task": worker_task,
            }

            # 运行 Worker
            worker_cfg = workers[worker_name]
            worker_output = ""
            async for event in self._run_single_agent(
                execution_id, session_id, worker_cfg,
                worker_run_ids[worker_name], worker_task,
                shared_context, lock,
            ):
                yield event
                if event.get("type") == "delta":
                    worker_output += event.get("content", "")

            # Worker 结果注入 Supervisor 下一轮
            messages.append({"role": "assistant", "content": full_output})
            messages.append({
                "role": "user",
                "content": f"[{worker_name} 完成]\n{worker_output}\n\n请继续根据以上结果完成任务。",
            })

        yield {"type": "multi_agent_done", "execution_id": execution_id, "mode": "supervisor"}

    # ─── Single Agent wrapper ─────────────────────────────────────────────────

    async def _run_single_agent(
        self,
        execution_id: str,
        session_id: str,
        agent_cfg: dict,
        run_id: str,
        input_content: str,
        shared_context: dict,
        lock: asyncio.Lock,
    ) -> AsyncIterator[dict]:
        agent_name = agent_cfg.get("name", run_id[:8])
        yield {
            "type": "agent_start",
            "agent_name": agent_name,
            "agent_index": agent_cfg.get("_index", 0),
            "run_id": run_id,
        }

        loop = AgentLoop(self.llm, self.tools)
        total_input_tokens = 0
        total_output_tokens = 0
        full_content = ""

        try:
            await self._update_run_status(run_id, "running")
            async for event in loop.run(
                session_id=f"{session_id}_{agent_name}",
                user_content=input_content,
                system_prompt_override=agent_cfg.get("system_prompt", ""),
                model_override=agent_cfg.get("model", ""),
                allowed_tools=agent_cfg.get("allowed_tools"),
            ):
                # 标注 agent_name，转发给前端
                patched = dict(event)
                patched["agent_name"] = agent_name
                patched["run_id"] = run_id
                yield patched

                if event.get("type") == "delta":
                    full_content += event.get("content", "")
                elif event.get("type") == "done":
                    meta = event.get("metadata") or {}
                    total_input_tokens = meta.get("input_tokens", 0) or 0
                    total_output_tokens = meta.get("output_tokens", 0) or 0

            # 写入 output_var
            output_var = agent_cfg.get("output_var")
            if output_var:
                async with lock:
                    shared_context[output_var] = full_content

            await self._finish_run(run_id, "done", total_input_tokens, total_output_tokens)
            yield {
                "type": "agent_done",
                "agent_name": agent_name,
                "run_id": run_id,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        except Exception as e:
            logger.exception(f"[AGENT ERROR] {agent_name}: {e}")
            await self._finish_run(run_id, "error", 0, 0, str(e))
            yield {
                "type": "agent_error",
                "agent_name": agent_name,
                "run_id": run_id,
                "message": str(e),
            }

    # ─── DB helpers ──────────────────────────────────────────────────────────

    async def _create_run(self, execution_id: str, agent_cfg: dict, idx: int) -> str:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        db = await get_db()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute(
                """INSERT INTO agent_runs
                   (id, execution_id, agent_name, agent_type, agent_index,
                    status, system_prompt, model, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    execution_id,
                    agent_cfg.get("name", f"agent_{idx}"),
                    agent_cfg.get("type", "llm"),
                    idx,
                    "idle",
                    agent_cfg.get("system_prompt", "")[:2000],
                    agent_cfg.get("model", ""),
                    now,
                ),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[AGENT RUN DB] create failed: {e}")
        return run_id

    async def _update_run_status(self, run_id: str, status: str) -> None:
        db = await get_db()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute(
                "UPDATE agent_runs SET status=?, started_at=? WHERE id=?",
                (status, now, run_id),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[AGENT RUN DB] update status failed: {e}")

    async def _finish_run(
        self,
        run_id: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        error: str = "",
    ) -> None:
        db = await get_db()
        now = datetime.now(timezone.utc).isoformat()
        try:
            await db.execute(
                """UPDATE agent_runs
                   SET status=?, finished_at=?, input_tokens=?, output_tokens=?, error=?
                   WHERE id=?""",
                (status, now, input_tokens, output_tokens, error or None, run_id),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"[AGENT RUN DB] finish failed: {e}")
