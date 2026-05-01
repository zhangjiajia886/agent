from __future__ import annotations

import logging
from typing import Any

from .base import BaseTool

logger = logging.getLogger(__name__)

from .builtin import (
    BashTool, ReadFileTool, WriteFileTool, GrepSearchTool, HttpRequestTool,
    PythonExecTool, WebSearchTool,
    EditFileTool, ListDirTool, FindFilesTool, WebFetchTool, TodoTool,
    InsertFileLineTool, UndoEditTool,
)
from .data_tools import ALL_DATA_TOOLS
from .diagram_tool import DrawDiagramTool
from .advanced_tools import ALL_ADVANCED_TOOLS
from .agent_tools import ALL_AGENT_TOOLS


# Common tool name aliases the LLM may hallucinate → (canonical_name, arg_transformer)
_TOOL_ALIASES: dict[str, tuple[str, Any]] = {
    # ── Python execution ──────────────────────────────────────────────────────
    "execute_code":          ("python_exec", None),
    "run_code":              ("python_exec", None),
    "run_python":            ("python_exec", None),
    "python":                ("python_exec", None),
    "python_repl":           ("python_exec", None),
    "jupyter":               ("python_exec", None),
    "notebook_execute":      ("python_exec", None),

    # ── Bash / shell ─────────────────────────────────────────────────────────
    "shell_exec":            ("bash", None),
    "run_shell":             ("bash", None),
    "shell":                 ("bash", None),
    "execute_bash":          ("bash", None),
    "terminal":              ("bash", None),
    "cmd":                   ("bash", None),
    "computer":              ("bash",  # Claude Code's computer use → bash
                              lambda a: {"command": a.get("input", a.get("command", ""))}),

    # ── File existence checks ────────────────────────────────────────────────
    "file_exists":           ("bash",
                              lambda a: {"command": f'test -f {repr(a.get("path",""))} && echo exists || echo not_found'}),
    "check_file_exists":     ("bash",
                              lambda a: {"command": f'test -f {repr(a.get("path",""))} && echo exists || echo not_found'}),
    "path_exists":           ("bash",
                              lambda a: {"command": f'test -e {repr(a.get("path",""))} && echo exists || echo not_found'}),

    # ── File operation dispatcher ────────────────────────────────────────────
    "file_operations":       ("_dispatch_file_op", None),
    "file_operation":        ("_dispatch_file_op", None),

    # ── Read file ────────────────────────────────────────────────────────────
    "read_file_content":     ("read_file", None),
    "load_file":             ("read_file", None),
    "open_file":             ("read_file", None),
    "cat_file":              ("read_file", None),
    "view":                  ("read_file",  # Claude Code's View tool
                              lambda a: {"path": a.get("path", a.get("file_path", ""))}),
    "view_file":             ("read_file", None),
    "show_file":             ("read_file", None),
    "read_document":         ("read_file", None),
    "notebook_read":         ("read_file",
                              lambda a: {"path": a.get("notebook_path", a.get("path", ""))}),

    # ── Write file ───────────────────────────────────────────────────────────
    "create_file":           ("write_file", None),
    "save_file":             ("write_file", None),
    "write_to_file":         ("write_file", None),
    "create_and_write":      ("write_file", None),
    "new_file":              ("write_file", None),
    "make_file":             ("write_file", None),
    "overwrite_file":        ("write_file", None),

    # ── Edit file ────────────────────────────────────────────────────────────
    "str_replace_editor":    ("edit_file",  # Claude Code's str_replace_editor
                              lambda a: {
                                  "path": a.get("path", ""),
                                  "old_string": a.get("old_str", a.get("old_string", "")),
                                  "new_string": a.get("new_str", a.get("new_string", "")),
                              }),
    "str_replace":           ("edit_file",
                              lambda a: {
                                  "path": a.get("path", ""),
                                  "old_string": a.get("old_str", a.get("old_string", "")),
                                  "new_string": a.get("new_str", a.get("new_string", "")),
                              }),
    "replace_in_file":       ("edit_file", None),
    "patch_file":            ("edit_file", None),
    "modify_file":           ("edit_file", None),
    "update_file":           ("edit_file", None),
    "insert_in_file":        ("edit_file",  # insert → write whole new content
                              lambda a: {"path": a.get("path",""), "old_string": "", "new_string": a.get("new_str", a.get("content",""))}),

    # ── Web search ───────────────────────────────────────────────────────────
    "search_web":            ("web_search", None),
    "internet_search":       ("web_search", None),
    "google_search":         ("web_search", None),
    "network_search":        ("web_search", None),   # Claude.ai alias
    "bing_search":           ("web_search", None),
    "web_lookup":            ("web_search", None),
    "search_internet":       ("web_search", None),
    "online_search":         ("web_search", None),
    "search_query":          ("web_search", None),
    "search":                ("web_search",
                              lambda a: {"query": a.get("query", a.get("q", a.get("keyword","")))}),

    # ── Web fetch ────────────────────────────────────────────────────────────
    "fetch_url":             ("web_fetch", None),
    "get_url":               ("web_fetch", None),
    "http_get":              ("web_fetch", None),
    "browse":                ("web_fetch", None),
    "open_url":              ("web_fetch", None),
    "visit_url":             ("web_fetch", None),
    "fetch_webpage":         ("web_fetch", None),
    "scrape":                ("web_fetch", None),

    # ── File search ──────────────────────────────────────────────────────────
    "search_files":          ("grep_search", None),
    "grep":                  ("grep_search", None),
    "find_in_files":         ("grep_search", None),
    "search_codebase":       ("grep_search", None),
    "code_search":           ("grep_search", None),
    "find_file":             ("find_files", None),
    "glob":                  ("find_files", None),
    "ls":                    ("list_dir",
                              lambda a: {"path": a.get("path", a.get("directory", "."))}),
    "list_directory":        ("list_dir", None),
    "listdir":               ("list_dir", None),
    "dir":                   ("list_dir", None),

    # ── HTTP requests ────────────────────────────────────────────────────────
    "make_request":          ("http_request", None),
    "api_call":              ("http_request", None),
    "curl":                  ("http_request",
                              lambda a: {"method": "GET", "url": a.get("url",""), "headers": {}}),
    "fetch":                 ("http_request",
                              lambda a: {"method": "GET", "url": a.get("url",""), "headers": {}}),
    "post_request":          ("http_request",
                              lambda a: {**a, "method": "POST"}),
    "get_request":           ("http_request",
                              lambda a: {**a, "method": "GET"}),
}


def _dispatch_file_op(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Route file_operations{operation, path, content?} to the right tool."""
    op = str(arguments.get("operation", "write")).lower()
    path = arguments.get("path", "")
    if op in ("read", "load", "open"):
        return "read_file", {"path": path}
    if op in ("delete", "remove"):
        return "bash", {"command": f"rm -f {repr(path)}"}
    if op in ("exists", "check"):
        return "bash", {"command": f'test -f {repr(path)} && echo exists || echo not_found'}
    # default: write
    return "write_file", {"path": path, "content": arguments.get("content", "")}


class ToolRegistry:
    """Unified registry for built-in tools and MCP tools."""

    def __init__(self):
        self._builtin: dict[str, BaseTool] = {}
        self._mcp_tools: dict[str, dict] = {}

    def register_builtin(self, tool: BaseTool) -> None:
        self._builtin[tool.name] = tool

    def register_defaults(self) -> None:
        for tool_cls in [
            BashTool, ReadFileTool, WriteFileTool, EditFileTool,
            InsertFileLineTool, UndoEditTool,
            GrepSearchTool, FindFilesTool, ListDirTool,
            HttpRequestTool, WebSearchTool, WebFetchTool,
            PythonExecTool, TodoTool, DrawDiagramTool,
        ]:
            self.register_builtin(tool_cls())
        for tool_cls in ALL_DATA_TOOLS:
            self.register_builtin(tool_cls())
        for tool_cls in ALL_ADVANCED_TOOLS:
            self.register_builtin(tool_cls())
        for tool_cls in ALL_AGENT_TOOLS:
            self.register_builtin(tool_cls())

    def get(self, name: str) -> BaseTool | None:
        return self._builtin.get(name)

    def get_schema(self, name: str) -> dict | None:
        tool = self._builtin.get(name)
        if tool:
            return tool.schema
        return self._mcp_tools.get(name)

    def list_all(self) -> list[dict]:
        tools = []
        for t in self._builtin.values():
            tools.append({
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "type": "builtin",
                "risk_level": t.risk_level,
                "input_schema": t.input_schema,
                "is_enabled": True,
            })
        for name, schema in self._mcp_tools.items():
            tools.append({
                "name": name,
                "description": schema.get("description", ""),
                "category": "mcp",
                "type": "mcp",
                "risk_level": "medium",
                "input_schema": schema.get("parameters", {}),
                "is_enabled": True,
            })
        return tools

    def register_mcp_tools(self, server_name: str, tools: list[dict]) -> None:
        for tool in tools:
            key = f"mcp_{server_name}_{tool['name']}"
            self._mcp_tools[key] = tool

    def unregister_mcp_tools(self, server_name: str) -> None:
        prefix = f"mcp_{server_name}_"
        self._mcp_tools = {k: v for k, v in self._mcp_tools.items() if not k.startswith(prefix)}

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name in self._builtin:
            return await self._builtin[tool_name].run(arguments)
        # Alias resolution
        if tool_name in _TOOL_ALIASES:
            canonical, transformer = _TOOL_ALIASES[tool_name]
            if canonical == "_dispatch_file_op":
                canonical, arguments = _dispatch_file_op(arguments)
            elif transformer is not None:
                arguments = transformer(arguments)
            logger.info(f"Tool alias: {tool_name!r} → {canonical!r}")
            if canonical in self._builtin:
                return await self._builtin[canonical].run(arguments)
        raise ValueError(f"Unknown tool: {tool_name}")
