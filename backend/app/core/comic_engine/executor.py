"""
工作流执行引擎 — DAG 拓扑排序 → 逐 batch 执行 → 断点恢复。
来源: backend-myagent2/app/engine/executor.py，适配漫剧 Agent 工具和 LLM。

改动:
  - 移除 skill/subflow 节点类型
  - _exec_tool() 调用漫剧 tool_executor.execute_tool()
  - _exec_llm() 调用漫剧 openai_client
  - WS 推送通过回调函数（不依赖 WSManager）
  - DB 改用 SQLAlchemy
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable, Optional

from loguru import logger

from .checkpoint import CheckpointManager
from .context import ExecutionContext
from .dag import topological_sort
from app.core.comic_chat_agent.openai_client import OpenAICompatClient
from app.core.comic_chat_agent.tool_executor import execute_tool


EventCallback = Callable[[dict], Awaitable[None]]


async def _noop_callback(event: dict) -> None:
    pass


class WorkflowEngine:
    """
    Workflow execution engine.
    - Parse JSON -> DAG -> topological sort
    - Batch-level parallel execution
    - Checkpoint save per batch
    - Event callback for real-time status push
    """

    def __init__(self, on_event: EventCallback = _noop_callback):
        self.on_event = on_event

    async def execute(
        self,
        execution_id: str,
        workflow: dict,
        inputs: dict[str, Any],
        resume: bool = False,
        llm_config: Optional[dict] = None,
    ) -> dict[str, Any]:
        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        edges = workflow.get("edges", [])
        variables = workflow.get("variables", {})

        ckpt_mgr = CheckpointManager(execution_id)
        completed_nodes: set[str] = set()
        node_statuses: dict[str, dict] = {}
        trace_spans: list[dict] = []

        if resume:
            ckpt = await ckpt_mgr.load()
            if ckpt:
                ctx = ExecutionContext.restore(ckpt["state"], inputs)
                completed_nodes = ckpt["completed_nodes"]
                node_statuses = dict(ctx.node_results)
                logger.info(f"[WFEngine] RESUME exec={execution_id} completed={len(completed_nodes)}")
            else:
                ctx = ExecutionContext(variables, inputs)
        else:
            ctx = ExecutionContext(variables, inputs)

        try:
            batches = topological_sort(nodes, edges)
        except ValueError as e:
            await self.on_event({"type": "execution_error", "execution_id": execution_id, "error": str(e)})
            return {"error": str(e), "node_statuses": node_statuses}

        await self.on_event({
            "type": "execution_started", "execution_id": execution_id,
            "resumed": resume and len(completed_nodes) > 0,
            "total_nodes": len(nodes), "total_batches": len(batches),
        })

        for batch in batches:
            pending = [nid for nid in batch if nid not in completed_nodes]
            if not pending:
                continue

            if len(pending) == 1:
                nid = pending[0]
                span = await self._execute_node(execution_id, nodes[nid], ctx, edges, trace_spans, llm_config)
                node_statuses[nid] = span
                ctx.record_node_result(nid, span)
            else:
                results = await asyncio.gather(*[
                    self._execute_node(execution_id, nodes[nid], ctx, edges, trace_spans, llm_config)
                    for nid in pending
                ], return_exceptions=True)
                for nid, result in zip(pending, results):
                    if isinstance(result, Exception):
                        node_statuses[nid] = {"status": "error", "error": str(result)}
                    else:
                        node_statuses[nid] = result
                    ctx.record_node_result(nid, node_statuses[nid])

            completed_nodes.update(pending)
            await ckpt_mgr.save(node_id=pending[-1], ctx=ctx, completed_nodes=completed_nodes)

        outputs = ctx.get_outputs()
        status = "done"
        if any(s.get("status") == "error" for s in node_statuses.values()):
            status = "error"

        await self.on_event({"type": "execution_finished", "execution_id": execution_id, "status": status})

        if status == "done":
            await ckpt_mgr.delete()

        return {"outputs": outputs, "node_statuses": node_statuses, "trace_spans": trace_spans, "status": status}

    async def _execute_node(self, execution_id, node, ctx, edges, trace_spans, llm_config=None):
        node_id = node["id"]
        node_type = node["type"]
        data = node.get("data", {})
        start_time = time.time()

        await self.on_event({"type": "node_status", "execution_id": execution_id, "node_id": node_id, "status": "running"})

        span_info: dict[str, Any] = {
            "span_id": str(uuid.uuid4())[:8], "node_id": node_id, "node_type": node_type,
            "start_time": datetime.now(timezone.utc).isoformat(), "status": "running",
        }

        try:
            result = None
            if node_type == "start":
                result = self._exec_start(node_id, data, ctx)
            elif node_type == "end":
                result = self._exec_end(data, ctx)
            elif node_type == "llm":
                result = await self._exec_llm(execution_id, node_id, data, ctx, llm_config)
            elif node_type == "tool":
                result = await self._exec_tool(data, ctx)
            elif node_type == "condition":
                result = self._exec_condition(data, ctx)
            elif node_type == "loop":
                result = await self._exec_loop(execution_id, node_id, data, ctx, edges, trace_spans, llm_config)
            elif node_type == "variable":
                result = self._exec_variable(data, ctx)
            elif node_type == "merge":
                result = self._exec_merge(data, ctx)

            output_var = data.get("outputVariable", "")
            if output_var and result is not None:
                ctx.set(output_var, result)

            elapsed_ms = int((time.time() - start_time) * 1000)
            span_info.update({"status": "done", "end_time": datetime.now(timezone.utc).isoformat(), "latency_ms": elapsed_ms, "result_preview": str(result)[:200] if result else ""})
            trace_spans.append(span_info)

            await self.on_event({"type": "node_status", "execution_id": execution_id, "node_id": node_id, "status": "done", "latency_ms": elapsed_ms})
            return {"status": "done", "latency_ms": elapsed_ms, "result_preview": str(result)[:200] if result else ""}

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            span_info.update({"status": "error", "end_time": datetime.now(timezone.utc).isoformat(), "latency_ms": elapsed_ms, "error": str(e)})
            trace_spans.append(span_info)
            await self.on_event({"type": "node_status", "execution_id": execution_id, "node_id": node_id, "status": "error", "error": str(e)})
            on_error = data.get("onError", "stop")
            if on_error == "stop":
                raise
            return {"status": "error", "error": str(e)}

    # ── 节点类型实现 ──

    def _exec_start(self, node_id, data, ctx):
        for var_name in data.get("outputs", []):
            val = ctx._raw_inputs.get(var_name, ctx.get(var_name, ""))
            ctx.set(var_name, val)
            ctx.set(f"{node_id}_{var_name}", val)

    def _exec_end(self, data, ctx):
        return {name: ctx.get(name) for name in data.get("outputs", [])}

    async def _exec_llm(self, execution_id, node_id, data, ctx, llm_config=None):
        system_prompt = ctx.render_template(data.get("systemPrompt", ""))
        user_message = ctx.render_template(data.get("userPromptTemplate", ""))
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_message:
            messages.append({"role": "user", "content": user_message})

        cfg = llm_config or {}
        model = data.get("model", "") or cfg.get("model", "")
        llm = OpenAICompatClient(base_url=cfg.get("base_url", ""), api_key=cfg.get("api_key", ""), model=model)

        full_text = ""
        async for text in llm.chat_stream(messages=messages, temperature=data.get("temperature", 0.7), max_tokens=data.get("maxTokens", 4096)):
            full_text += text
            await self.on_event({"type": "llm_stream", "execution_id": execution_id, "node_id": node_id, "delta": text})
        return full_text

    async def _exec_tool(self, data, ctx):
        tool_name = data.get("toolName", "")
        arguments = dict(data.get("toolParams", {}))
        for param_key, var_name in data.get("paramMapping", {}).items():
            arguments[param_key] = ctx.get(var_name)
        for key, val in arguments.items():
            if isinstance(val, str) and "{{" in val:
                arguments[key] = ctx.render_template(val)
        result = await execute_tool(tool_name, arguments)
        if isinstance(result, dict) and result.get("status") == "error":
            raise RuntimeError(result.get("error", "工具执行失败"))
        return result

    def _exec_condition(self, data, ctx):
        for branch in data.get("branches", []):
            condition = branch.get("condition", "")
            try:
                rendered = ctx.render_template(condition)
                if eval(rendered, {"__builtins__": {}}, ctx.variables):
                    return branch.get("targetHandle", branch.get("id", ""))
            except Exception:
                continue
        return data.get("defaultBranch", "default")

    async def _exec_loop(self, execution_id, node_id, data, ctx, edges, trace_spans, llm_config=None):
        max_iter = data.get("maxIterations", 10)
        exit_cond = data.get("exitCondition", "false")
        ctx_var = data.get("contextVariable", "loop_result")
        append_mode = data.get("appendMode", "replace")

        for i in range(max_iter):
            await self.on_event({"type": "loop_iteration", "execution_id": execution_id, "node_id": node_id, "iteration": i + 1})
            body_nodes = data.get("bodyNodes", [])
            body_edges = data.get("bodyEdges", [])
            if body_nodes:
                sub = WorkflowEngine(on_event=self.on_event)
                sub_result = await sub.execute(execution_id, {"nodes": body_nodes, "edges": body_edges, "variables": {}}, ctx.variables, llm_config=llm_config)
                body_result = sub_result.get("outputs", {})
            else:
                body_result = None
            if body_result is not None:
                if append_mode == "append":
                    ctx.append_to(ctx_var, body_result)
                else:
                    ctx.set(ctx_var, body_result)
            try:
                rendered = ctx.render_template(exit_cond)
                if eval(rendered, {"__builtins__": {}}, ctx.variables):
                    break
            except Exception:
                pass
        return ctx.get(ctx_var)

    def _exec_variable(self, data, ctx):
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

    def _exec_merge(self, data, ctx):
        merge_vars = data.get("mergeVariables", [])
        strategy = data.get("strategy", "concat")
        results = {var: ctx.get(var) for var in merge_vars}
        if strategy == "concat" and all(isinstance(v, str) for v in results.values()):
            return {"merged": "\n".join(str(v) for v in results.values())}
        return results
