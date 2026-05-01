from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import json as _json

from ..db.database import get_db
from ..llm.client import LLMClient, LLMStreamChunk
from .checkpoint import CheckpointManager
from ..tools.registry import ToolRegistry
from ..ws.manager import WSManager
from ..core.cancellation import CancellationToken
from .context import ExecutionContext
from .dag import topological_sort

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Workflow execution engine.
    - Parse JSON -> DAG
    - Topological sort for execution order
    - Schedule nodes by dependency
    - WebSocket push real-time status
    """

    def __init__(self, llm: LLMClient, tools: ToolRegistry, ws: WSManager):
        self.llm = llm
        self.tools = tools
        self.ws = ws

    async def execute(
        self,
        execution_id: str,
        workflow: dict,
        inputs: dict[str, Any],
        cancel_token: CancellationToken | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        cancel_token = cancel_token or CancellationToken()

        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        edges = workflow.get("edges", [])
        variables = workflow.get("variables", {})

        ckpt_mgr = CheckpointManager(execution_id)
        completed_nodes: set[str] = set()
        node_statuses: dict[str, dict] = {}
        trace_spans: list[dict] = []

        # ── 断点恢复：加载 checkpoint ──
        if resume:
            ckpt = await ckpt_mgr.load()
            if ckpt:
                ctx = ExecutionContext.restore(ckpt["state"], inputs)
                completed_nodes = ckpt["completed_nodes"]
                node_statuses = dict(ctx.node_results)
                logger.info(
                    f"[RESUME] exec={execution_id} "
                    f"restoring from node={ckpt['node_id']} "
                    f"completed={len(completed_nodes)} nodes"
                )
            else:
                ctx = ExecutionContext(variables, inputs)
                logger.info(f"[RESUME] exec={execution_id} no checkpoint found, starting fresh")
        else:
            ctx = ExecutionContext(variables, inputs)

        try:
            batches = topological_sort(nodes, edges)
        except ValueError as e:
            await self.ws.emit("execution_error", {
                "execution_id": execution_id, "error": str(e)
            }, execution_id)
            return {"error": str(e), "node_statuses": node_statuses}

        await self.ws.emit("execution_started", {
            "execution_id": execution_id,
            "resumed": resume and len(completed_nodes) > 0,
            "completed_nodes": list(completed_nodes),
        }, execution_id)

        for batch in batches:
            if cancel_token.is_cancelled:
                for nid in batch:
                    node_statuses[nid] = {"status": "skipped"}
                continue

            # ── 跳过已完成节点 ──
            pending_nodes = [nid for nid in batch if nid not in completed_nodes]
            if not pending_nodes:
                logger.debug(f"[RESUME SKIP] exec={execution_id} batch={batch} all completed")
                continue

            if len(pending_nodes) == 1:
                nid = pending_nodes[0]
                span = await self._execute_node(
                    execution_id, nodes[nid], ctx, edges, cancel_token, trace_spans
                )
                node_statuses[nid] = span
                ctx.record_node_result(nid, span)
            else:
                results = await asyncio.gather(*[
                    self._execute_node(
                        execution_id, nodes[nid], ctx, edges, cancel_token, trace_spans
                    )
                    for nid in pending_nodes
                ], return_exceptions=True)
                for nid, result in zip(pending_nodes, results):
                    if isinstance(result, Exception):
                        node_statuses[nid] = {"status": "error", "error": str(result)}
                    else:
                        node_statuses[nid] = result
                    ctx.record_node_result(nid, node_statuses[nid])

            # ── 每个 batch 完成后保存 checkpoint ──
            completed_nodes.update(pending_nodes)
            await ckpt_mgr.save(
                node_id=pending_nodes[-1],
                ctx=ctx,
                completed_nodes=completed_nodes,
            )

        outputs = ctx.get_outputs()
        status = "cancelled" if cancel_token.is_cancelled else "done"

        if any(s.get("status") == "error" for s in node_statuses.values()):
            status = "error"

        await self.ws.emit("execution_finished", {
            "execution_id": execution_id,
            "status": status,
        }, execution_id)

        return {
            "outputs": outputs,
            "node_statuses": node_statuses,
            "trace_spans": trace_spans,
            "status": status,
        }

    async def _execute_node(
        self,
        execution_id: str,
        node: dict,
        ctx: ExecutionContext,
        edges: list[dict],
        cancel_token: CancellationToken,
        trace_spans: list[dict],
    ) -> dict:
        node_id = node["id"]
        node_type = node["type"]
        data = node.get("data", {})

        span_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        await self.ws.emit("node_status", {
            "execution_id": execution_id,
            "id": node_id,
            "status": "running",
        }, execution_id)

        span_info: dict[str, Any] = {
            "span_id": span_id,
            "node_id": node_id,
            "node_type": node_type,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

        try:
            if cancel_token.is_cancelled:
                span_info["status"] = "cancelled"
                return {"status": "cancelled"}

            result = None

            if node_type == "start":
                result = self._exec_start(node_id, data, ctx)
            elif node_type == "end":
                result = self._exec_end(data, ctx)
            elif node_type == "llm":
                result = await self._exec_llm(execution_id, node_id, data, ctx, cancel_token)
                span_info["model"] = data.get("model", "")
            elif node_type == "tool":
                result = await self._exec_tool(data, ctx, cancel_token)
                span_info["tool_name"] = data.get("toolName", "")
            elif node_type == "condition":
                result = self._exec_condition(data, ctx)
            elif node_type == "loop":
                result = await self._exec_loop(
                    execution_id, node_id, data, ctx, edges, cancel_token, trace_spans
                )
            elif node_type == "variable":
                result = self._exec_variable(data, ctx)
            elif node_type == "merge":
                result = self._exec_merge(data, ctx)
            elif node_type == "skill":
                result = await self._exec_skill(
                    execution_id, node_id, data, ctx, cancel_token
                )
                span_info["skill_id"] = data.get("skillId", "")
            elif node_type == "subflow":
                result = {"note": "subflow execution not yet implemented"}

            output_var = data.get("outputVariable", "")
            if output_var and result is not None:
                ctx.set(output_var, result)

            elapsed_ms = int((time.time() - start_time) * 1000)
            span_info.update({
                "status": "done",
                "end_time": datetime.now(timezone.utc).isoformat(),
                "latency_ms": elapsed_ms,
                "result_preview": str(result)[:200] if result else "",
            })
            trace_spans.append(span_info)

            await self.ws.emit("node_status", {
                "execution_id": execution_id,
                "id": node_id,
                "status": "done",
                "latency_ms": elapsed_ms,
                "result_preview": str(result)[:200] if result else "",
            }, execution_id)

            return {
                "status": "done",
                "latency_ms": elapsed_ms,
                "result_preview": str(result)[:200] if result else "",
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            span_info.update({
                "status": "error",
                "end_time": datetime.now(timezone.utc).isoformat(),
                "latency_ms": elapsed_ms,
                "error": str(e),
            })
            trace_spans.append(span_info)

            await self.ws.emit("node_status", {
                "execution_id": execution_id,
                "id": node_id,
                "status": "error",
                "error": str(e),
            }, execution_id)

            on_error = data.get("onError", "stop")
            if on_error == "stop":
                raise
            return {"status": "error", "error": str(e)}

    def _exec_start(self, node_id: str, data: dict, ctx: ExecutionContext) -> None:
        outputs = data.get("outputs", [])
        for var_name in outputs:
            val = ctx._raw_inputs.get(var_name, ctx.get(var_name, ""))
            ctx.set(var_name, val)
            # Dify-style alias: {{nodeId_varName}} e.g. {{1721105947247_content}}
            ctx.set(f"{node_id}_{var_name}", val)
        return None

    def _exec_end(self, data: dict, ctx: ExecutionContext) -> dict:
        outputs = data.get("outputs", [])
        return {name: ctx.get(name) for name in outputs}

    async def _exec_llm(
        self,
        execution_id: str,
        node_id: str,
        data: dict,
        ctx: ExecutionContext,
        cancel_token: CancellationToken,
    ) -> str:
        system_prompt = ctx.render_template(data.get("systemPrompt", ""))
        user_message = ctx.render_template(data.get("userPromptTemplate", ""))

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_message:
            messages.append({"role": "user", "content": user_message})

        tools = None
        if data.get("enableTools"):
            allowed = data.get("allowedTools", [])
            tools = [self.tools.get_schema(t) for t in allowed if self.tools.get_schema(t)]

        model = data.get("model", "") or ""
        if not model or model == "default":
            from ..core.config import get_settings
            model = get_settings().llm_default_model or "qwen3-32b"
        temperature = data.get("temperature", 0.7)
        max_tokens = data.get("maxTokens", 2048)

        result_iter = await self.llm.chat(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        full_text = ""
        async for chunk in result_iter:
            if cancel_token.is_cancelled:
                break
            if isinstance(chunk, LLMStreamChunk) and chunk.text:
                full_text += chunk.text
                await self.ws.emit("llm_stream", {
                    "execution_id": execution_id,
                    "node_id": node_id,
                    "delta": chunk.text,
                }, execution_id)

        return full_text

    async def _exec_tool(
        self,
        data: dict,
        ctx: ExecutionContext,
        cancel_token: CancellationToken,
    ) -> Any:
        tool_name = data.get("toolName", "")
        static_params = data.get("toolParams", {})
        param_mapping = data.get("paramMapping", {})

        arguments = dict(static_params)
        for param_key, var_name in param_mapping.items():
            arguments[param_key] = ctx.get(var_name)

        for key, val in arguments.items():
            if isinstance(val, str) and "{{" in val:
                arguments[key] = ctx.render_template(val)

        if cancel_token.is_cancelled:
            return {"error": "Cancelled"}

        return await self.tools.execute(tool_name, arguments)

    def _exec_condition(self, data: dict, ctx: ExecutionContext) -> str:
        branches = data.get("branches", [])
        for branch in branches:
            condition = branch.get("condition", "")
            try:
                rendered = ctx.render_template(condition)
                if eval(rendered, {"__builtins__": {}}, ctx.variables):
                    return branch.get("targetHandle", branch.get("id", ""))
            except Exception:
                continue
        return data.get("defaultBranch", "default")

    async def _exec_loop(
        self,
        execution_id: str,
        node_id: str,
        data: dict,
        ctx: ExecutionContext,
        edges: list[dict],
        cancel_token: CancellationToken,
        trace_spans: list[dict],
    ) -> Any:
        max_iterations = data.get("maxIterations", 10)
        exit_condition = data.get("exitCondition", "false")
        context_var = data.get("contextVariable", "loop_result")
        append_mode = data.get("appendMode", "replace")

        for i in range(max_iterations):
            if cancel_token.is_cancelled:
                break

            await self.ws.emit("loop_iteration", {
                "execution_id": execution_id,
                "node_id": node_id,
                "iteration": i + 1,
                "status": "running",
            }, execution_id)

            body_nodes = data.get("bodyNodes", [])
            body_edges = data.get("bodyEdges", [])
            if body_nodes:
                sub_engine = WorkflowEngine(self.llm, self.tools, self.ws)
                sub_result = await sub_engine.execute(
                    execution_id,
                    {"nodes": body_nodes, "edges": body_edges, "variables": {}},
                    ctx.variables,
                    cancel_token,
                )
                body_result = sub_result.get("outputs", {})
            else:
                body_result = None

            if body_result is not None:
                if append_mode == "append":
                    ctx.append_to(context_var, body_result)
                else:
                    ctx.set(context_var, body_result)

            try:
                rendered = ctx.render_template(exit_condition)
                if eval(rendered, {"__builtins__": {}}, ctx.variables):
                    break
            except Exception:
                pass

        return ctx.get(context_var)

    def _exec_variable(self, data: dict, ctx: ExecutionContext) -> Any:
        expression = data.get("expression", "")
        output_var = data.get("outputVariable", "")
        if expression:
            rendered = ctx.render_template(expression)
            try:
                result = eval(rendered, {"__builtins__": {}}, ctx.variables)
            except Exception:
                result = rendered
            if output_var:
                ctx.set(output_var, result)
            return result
        return None

    def _exec_merge(self, data: dict, ctx: ExecutionContext) -> dict:
        merge_vars = data.get("mergeVariables", [])
        strategy = data.get("strategy", "concat")
        results = {}
        for var_name in merge_vars:
            results[var_name] = ctx.get(var_name)
        if strategy == "concat" and all(isinstance(v, str) for v in results.values()):
            return {"merged": "\n".join(str(v) for v in results.values())}
        return results

    async def _exec_skill(
        self,
        execution_id: str,
        node_id: str,
        data: dict,
        ctx: ExecutionContext,
        cancel_token: CancellationToken,
    ) -> str:
        skill_id = data.get("skillId", "")
        if not skill_id:
            raise ValueError("SkillNode missing skillId")

        db = await get_db()
        row = await db.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
        skill = await row.fetchone()
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        skill = dict(skill)

        content = skill.get("content", "")
        args_template = data.get("argsTemplate", "")
        if args_template:
            rendered_args = ctx.render_template(args_template)
            content = content.replace("$ARGUMENTS", rendered_args)

        variables_raw = skill.get("variables", "[]")
        if isinstance(variables_raw, str):
            variables_raw = _json.loads(variables_raw)
        for var in variables_raw:
            content = content.replace(f"{{{{{var}}}}}", str(ctx.get(var, "")))

        allowed_tools_raw = skill.get("allowed_tools", "[]")
        if isinstance(allowed_tools_raw, str):
            allowed_tools_raw = _json.loads(allowed_tools_raw)

        model_override = data.get("modelOverride", "") or skill.get("model", "") or ""
        if not model_override or model_override == "default":
            from ..core.config import get_settings
            model_override = get_settings().llm_default_model or "qwen3-32b"

        messages: list[dict] = [
            {"role": "system", "content": content},
        ]
        user_input = ctx.render_template(data.get("userPromptTemplate", ""))
        if user_input:
            messages.append({"role": "user", "content": user_input})

        tools = None
        if allowed_tools_raw:
            tools = [self.tools.get_schema(t) for t in allowed_tools_raw if self.tools.get_schema(t)]

        result_iter = await self.llm.chat(
            model=model_override,
            messages=messages,
            tools=tools,
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("maxTokens", 4096),
            stream=True,
        )

        full_text = ""
        async for chunk in result_iter:
            if cancel_token.is_cancelled:
                break
            if isinstance(chunk, LLMStreamChunk) and chunk.text:
                full_text += chunk.text
                await self.ws.emit("llm_stream", {
                    "execution_id": execution_id,
                    "node_id": node_id,
                    "delta": chunk.text,
                }, execution_id)

        inv_id = f"inv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        elapsed_ms = 0
        try:
            await db.execute(
                """INSERT INTO skill_invocations
                   (id,skill_id,session_id,execution_mode,args_text,status,duration_ms,result_preview,invoked_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (inv_id, skill_id, execution_id,
                 skill.get("context_mode", ""), args_template,
                 "success", elapsed_ms, full_text[:500], now),
            )
            await db.commit()
        except Exception:
            pass

        return full_text
