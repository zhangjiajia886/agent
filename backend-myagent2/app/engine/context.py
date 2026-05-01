from __future__ import annotations

import re
from typing import Any


class ExecutionContext:
    """Workflow execution context — variable storage and template rendering."""

    def __init__(self, variable_defs: dict[str, Any], inputs: dict[str, Any]):
        self.variables: dict[str, Any] = {}
        self._raw_inputs: dict[str, Any] = dict(inputs)
        # Load all user inputs directly into variables first
        self.variables.update(inputs)
        # Then apply schema defaults for anything not provided
        for name, schema in variable_defs.items():
            if name not in self.variables:
                if isinstance(schema, dict):
                    self.variables[name] = schema.get("default", "")
                else:
                    self.variables[name] = schema
        self.message_histories: dict[str, list[dict]] = {}
        self.node_results: dict[str, dict] = {}

    def set(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def render_template(self, template: str) -> str:
        """Replace {{variable}} with actual values, supporting nested a.b.c paths."""
        def replacer(match: re.Match) -> str:
            var_path = match.group(1).strip()
            value: Any = self.variables
            for key in var_path.split("."):
                if isinstance(value, dict):
                    value = value.get(key, f"{{{{{var_path}}}}}")
                else:
                    return f"{{{{{var_path}}}}}"
            return str(value) if value is not None else ""
        return re.sub(r"\{\{(.+?)\}\}", replacer, template)

    def append_to(self, name: str, value: Any) -> None:
        current = self.variables.get(name)
        if isinstance(current, list):
            current.append(value)
        elif isinstance(current, str):
            current += "\n" + str(value)
        else:
            current = [value]
        self.variables[name] = current

    def record_node_result(self, node_id: str, result: dict) -> None:
        """节点完成时调用，供 CheckpointManager 序列化。"""
        self.node_results[node_id] = result

    @classmethod
    def restore(cls, state: dict, inputs: dict[str, Any]) -> "ExecutionContext":
        """从 checkpoint state 恢复 context，跳过重新执行已完成节点。"""
        ctx = cls(state.get("variables", {}), inputs)
        ctx.variables.update(state.get("variables", {}))
        ctx.node_results = state.get("node_results", {})
        return ctx

    def get_outputs(self) -> dict[str, Any]:
        return dict(self.variables)
