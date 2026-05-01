from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from .base import BaseTool

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}
_DOC_EXTS = {".pdf", ".xlsx", ".xls", ".csv", ".html", ".docx", ".pptx"}
_WATCH_DIRS = ["/tmp", str(Path.home()), "/var/tmp"]
_edit_history: dict[str, str] = {}  # path → content before last edit_file run
_OUTPUTS_DIR = Path("static/outputs")
_MAX_TOOL_OUTPUT_CHARS = 8_192
_TRUNCATION_HINT = "\n\n⚠️ 输出已截断。大结果请写入 /tmp/result.json；图片请保存为 /tmp/*.png，系统会自动识别并展示。"


def _snapshot(directory: str) -> set[str]:
    try:
        return {os.path.join(directory, f) for f in os.listdir(directory)}
    except Exception:
        return set()


def _expose_file(src: str) -> str | None:
    try:
        _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        dest_name = f"{uuid.uuid4().hex[:8]}_{Path(src).name}"
        dest = _OUTPUTS_DIR / dest_name
        shutil.copy2(src, dest)
        return f"/api/outputs/{dest_name}"
    except Exception:
        return None


def _collect_new_files(snapshots_before: dict[str, set[str]]) -> list[dict]:
    results = []
    for watch_dir, before in snapshots_before.items():
        after = _snapshot(watch_dir)
        for new_file in after - before:
            ext = Path(new_file).suffix.lower()
            if ext in _IMAGE_EXTS:
                media_type = "image"
            elif ext in _DOC_EXTS:
                media_type = "document"
            else:
                continue
            url = _expose_file(new_file)
            if url:
                results.append({"url": url, "name": Path(new_file).name, "type": media_type})
    return results


def _truncate_tool_output(text: str) -> str:
    if len(text) <= _MAX_TOOL_OUTPUT_CHARS:
        return text
    return text[:_MAX_TOOL_OUTPUT_CHARS] + _TRUNCATION_HINT


def _extract_inline_images(text: str) -> tuple[str, list[dict[str, str]]]:
    file_urls: list[dict[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        ext = match.group(1).lower()
        payload = match.group(2)
        try:
            raw = base64.b64decode(payload, validate=True)
        except Exception:
            return match.group(0)
        out_path = Path("/tmp") / f"inline_image_{uuid.uuid4().hex[:8]}.{ext}"
        out_path.write_bytes(raw)
        url = _expose_file(str(out_path))
        if url:
            file_urls.append({"url": url, "name": out_path.name, "type": "image"})
        return f"[inline image extracted to {out_path}]"

    cleaned = re.sub(r"data:image/(png|jpeg|jpg|gif|webp|svg\+xml);base64,([A-Za-z0-9+/=\n\r]+)", _replace, text)
    return cleaned, file_urls


class BashTool(BaseTool):
    name = "bash"
    description = "Execute a shell command"
    category = "shell"
    risk_level = "high"

    BLOCKED_PATTERNS = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:"]

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                "working_dir": {"type": "string", "description": "Working directory"},
            },
            "required": ["command"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        command = arguments["command"]
        timeout = arguments.get("timeout", 30)
        cwd = arguments.get("working_dir", None)

        for pattern in self.BLOCKED_PATTERNS:
            if pattern in command:
                return {"error": f"Blocked dangerous command: {pattern}", "code": -1}

        watch_dirs = [d for d in _WATCH_DIRS if os.path.isdir(d)]
        if cwd and os.path.isdir(cwd):
            watch_dirs.append(cwd)
        snapshots = {d: _snapshot(d) for d in watch_dirs}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            result: dict[str, Any] = {
                "stdout": _truncate_tool_output(stdout.decode(errors="replace")),
                "stderr": _truncate_tool_output(stderr.decode(errors="replace")),
                "code": proc.returncode,
            }
            file_urls = _collect_new_files(snapshots)
            if file_urls:
                result["file_urls"] = file_urls
            return result
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"Command timed out after {timeout}s", "code": -1}
        except Exception as e:
            return {"error": str(e), "code": -1}


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read content from a file"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "offset": {"type": "integer", "description": "Line offset (1-indexed)"},
                "limit": {"type": "integer", "description": "Number of lines to read"},
            },
            "required": ["path"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        offset = arguments.get("offset", 1)
        limit = arguments.get("limit")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(0, offset - 1)
            end = start + limit if limit else len(lines)
            content = "".join(lines[start:end])
            return {"content": content, "total_lines": len(lines)}
        except Exception as e:
            return {"error": str(e)}


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        content = arguments["content"]
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "bytes_written": len(content.encode("utf-8"))}
        except Exception as e:
            return {"error": str(e)}


class GrepSearchTool(BaseTool):
    name = "grep_search"
    description = "Search for patterns in files"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search pattern (regex)"},
                "path": {"type": "string", "description": "Directory or file to search"},
                "includes": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns to include"},
            },
            "required": ["query", "path"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments["query"]
        path = arguments["path"]
        includes = arguments.get("includes", [])
        cmd = f'grep -rn "{query}" "{path}"'
        if includes:
            for inc in includes:
                cmd += f' --include="{inc}"'
        cmd += " | head -50"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), 15)
            return {"matches": stdout.decode(errors="replace")[:50_000]}
        except Exception as e:
            return {"error": str(e)}


class HttpRequestTool(BaseTool):
    name = "http_request"
    description = "Make an HTTP request"
    category = "network"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Request URL"},
                "method": {"type": "string", "description": "HTTP method", "default": "GET"},
                "headers": {"type": "object", "description": "Request headers"},
                "body": {"type": "string", "description": "Request body"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["url"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import httpx
        url = arguments["url"]
        method = arguments.get("method", "GET").upper()
        headers = arguments.get("headers", {})
        body = arguments.get("body")
        timeout = arguments.get("timeout", 30)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method, url, headers=headers, content=body, timeout=timeout
                )
                return {
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp.text[:50_000],
                }
        except Exception as e:
            return {"error": str(e)}


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "Execute Python code"
    category = "execution"
    risk_level = "high"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["code"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        code = (arguments.get("code") or arguments.get("script") or arguments.get("python") or arguments.get("cmd") or "").strip()
        if not code:
            return {"error": "缺少 code 参数"}
        timeout = arguments.get("timeout", 60)
        # Run in /tmp so relative-path saves (e.g. plt.savefig('x.png')) land there
        _exec_cwd = "/tmp"
        watch_dirs = list(_WATCH_DIRS) + [_exec_cwd]
        snapshots = {d: _snapshot(d) for d in dict.fromkeys(watch_dirs) if os.path.isdir(d)}
        # Write code to a temp file and run with python3 <file> to avoid
        # `-c` argument parsing issues (e.g. line-continuation SyntaxError)
        import tempfile
        tmp_script = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=_exec_cwd, delete=False, encoding="utf-8"
        )
        try:
            tmp_script.write(code)
            tmp_script.close()
            proc = await asyncio.create_subprocess_exec(
                "python3", tmp_script.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=_exec_cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            stdout_text, extracted_file_urls = _extract_inline_images(stdout.decode(errors="replace"))
            result: dict[str, Any] = {
                "stdout": _truncate_tool_output(stdout_text),
                "stderr": _truncate_tool_output(stderr.decode(errors="replace")),
                "code": proc.returncode,
            }
            file_urls = _collect_new_files(snapshots)
            if extracted_file_urls:
                file_urls.extend(extracted_file_urls)
            if file_urls:
                result["file_urls"] = file_urls
            return result
        except asyncio.TimeoutError:
            proc.kill()
            return {"error": f"Execution timed out after {timeout}s", "code": -1}
        except Exception as e:
            return {"error": str(e), "code": -1}
        finally:
            try:
                os.unlink(tmp_script.name)
            except Exception:
                pass


class EditFileTool(BaseTool):
    """str_replace based file editing — same as Claude Code's Edit tool."""
    name = "edit_file"
    description = "精确替换文件中的指定文本片段（str_replace）；必须先用 read_file 获取文件内容"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "old_string": {"type": "string", "description": "要替换的原始文本（必须在文件中唯一存在）"},
                "new_string": {"type": "string", "description": "替换后的新文本"},
            },
            "required": ["path", "old_string", "new_string"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        old = arguments["old_string"]
        new = arguments["new_string"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            count = content.count(old)
            if count == 0:
                return {"error": f"old_string 在文件中未找到"}
            if count > 1:
                return {"error": f"old_string 在文件中出现 {count} 次，请提供更多上下文使其唯一"}
            _edit_history[path] = content  # save for undo
            new_content = content.replace(old, new, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"error": str(e)}


class InsertFileLineTool(BaseTool):
    """Insert content before a specific line number."""
    name = "insert_file_line"
    description = "在文件指定行号前插入内容；先用 read_file 确认行号"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "line": {"type": "integer", "description": "在此行号**前**插入（1-indexed）；超出范围时追加到末尾"},
                "content": {"type": "string", "description": "要插入的内容（不需要尾部换行，工具自动处理）"},
            },
            "required": ["path", "line", "content"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        line = int(arguments["line"])
        content = arguments["content"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            _edit_history[path] = "".join(lines)  # save for undo
            insert_text = content if content.endswith("\n") else content + "\n"
            idx = max(0, min(line - 1, len(lines)))
            lines.insert(idx, insert_text)
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return {"ok": True, "path": path, "inserted_at_line": idx + 1, "total_lines": len(lines)}
        except Exception as e:
            return {"error": str(e)}


class UndoEditTool(BaseTool):
    """Revert the last edit_file or insert_file_line change for a file."""
    name = "undo_edit"
    description = "撤销对某个文件最近一次 edit_file 或 insert_file_line 的修改"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要撤销的文件路径"},
            },
            "required": ["path"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        if path not in _edit_history:
            return {"error": f"没有找到 {path} 的编辑历史，无法撤销"}
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(_edit_history.pop(path))
            return {"ok": True, "path": path, "message": "已撤销到上次 edit_file 之前的状态"}
        except Exception as e:
            return {"error": str(e)}


class ListDirTool(BaseTool):
    """List directory contents — same as Claude Code's LS tool."""
    name = "list_dir"
    description = "列出目录内容，返回文件和子目录（含大小和类型）"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"},
                "max_depth": {"type": "integer", "description": "最大递归深度（默认1）", "default": 1},
            },
            "required": ["path"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import os
        path = arguments["path"]
        max_depth = int(arguments.get("max_depth", 1))

        def _scan(p: str, depth: int) -> list[dict]:
            items = []
            try:
                for entry in sorted(os.scandir(p), key=lambda e: (not e.is_dir(), e.name)):
                    try:
                        stat = entry.stat()
                        item: dict[str, Any] = {
                            "name": entry.name,
                            "type": "directory" if entry.is_dir() else "file",
                            "path": entry.path,
                        }
                        if entry.is_file():
                            item["size"] = stat.st_size
                        elif entry.is_dir() and depth < max_depth:
                            item["children"] = _scan(entry.path, depth + 1)
                        items.append(item)
                    except PermissionError:
                        pass
            except PermissionError:
                pass
            return items

        try:
            if not os.path.isdir(path):
                return {"error": f"路径不存在或不是目录: {path}"}
            return {"path": path, "items": _scan(path, 1)}
        except Exception as e:
            return {"error": str(e)}


class FindFilesTool(BaseTool):
    """Glob-based file search — same as Claude Code's Glob tool."""
    name = "find_files"
    description = "按 glob 模式搜索文件（支持 *, **, ?），返回匹配的文件路径列表"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "glob 模式，如 '**/*.py' 或 'src/*.ts'"},
                "base_dir": {"type": "string", "description": "搜索起始目录（默认当前目录）", "default": "."},
                "max_results": {"type": "integer", "description": "最大返回数量（默认50）", "default": 50},
            },
            "required": ["pattern"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import glob as _glob
        import os
        pattern = arguments["pattern"]
        base_dir = arguments.get("base_dir", ".")
        max_results = int(arguments.get("max_results", 50))
        try:
            full_pattern = os.path.join(base_dir, pattern)
            matches = _glob.glob(full_pattern, recursive=True)[:max_results]
            return {"matches": sorted(matches), "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}


class WebFetchTool(BaseTool):
    """Fetch and extract text from a URL — similar to Claude Code's WebFetch."""
    name = "web_fetch"
    description = "获取网页或 URL 内容，提取纯文本（自动去除 HTML 标签）"
    category = "network"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要获取的 URL"},
                "max_chars": {"type": "integer", "description": "返回最大字符数（默认8000）", "default": 8000},
            },
            "required": ["url"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import httpx
        url = arguments["url"]
        max_chars = int(arguments.get("max_chars", 8000))
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
                resp = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
                ct = resp.headers.get("content-type", "")
                if "html" in ct:
                    text = re.sub(r"<style[^>]*>.*?</style>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                else:
                    text = resp.text
                return {"url": url, "content": text[:max_chars], "status": resp.status_code}
        except Exception as e:
            return {"error": str(e), "url": url}


_TODO_FILE = os.path.join(os.path.expanduser("~"), ".agentflow_todos.json")


class TodoTool(BaseTool):
    """Read/write a simple todo list — same as Claude Code's TodoRead/TodoWrite."""
    name = "todo"
    description = "读写任务列表；action='read' 查看，action='write' 更新（传入 todos JSON 数组）"
    category = "productivity"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write"], "description": "'read' 或 'write'"},
                "todos": {
                    "type": "array",
                    "description": "任务列表（action=write 时必填）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "content": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        },
                    },
                },
            },
            "required": ["action"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import json as _json
        action = arguments["action"]
        try:
            if action == "read":
                if not os.path.exists(_TODO_FILE):
                    return {"todos": []}
                with open(_TODO_FILE) as f:
                    return {"todos": _json.load(f)}
            else:
                todos = arguments.get("todos", [])
                with open(_TODO_FILE, "w") as f:
                    _json.dump(todos, f, ensure_ascii=False, indent=2)
                return {"ok": True, "count": len(todos)}
        except Exception as e:
            return {"error": str(e)}


_WEATHER_RE = re.compile(
    r"(天气|weather|气温|forecast|晴|雨|温度|humid|wind|雪|fog|云)",
    re.IGNORECASE,
)
_CITY_RE = re.compile(
    r"(上海|北京|广州|深圳|成都|杭州|武汉|南京|重庆|西安|苏州|天津|浦东|浦西|徐汇|黄浦"
    r"|[A-Za-z ]{3,}(?=.*天气|.*weather))",
    re.IGNORECASE,
)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索网络获取最新信息；天气查询自动使用实时天气服务"
    category = "network"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "num_results": {"type": "integer", "description": "返回结果数量（默认5）", "default": 5},
            },
            "required": ["query"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import httpx
        query = arguments["query"]
        num = min(int(arguments.get("num_results", 5)), 10)

        # ── Weather shortcut via wttr.in ──────────────────────────────────────
        if _WEATHER_RE.search(query):
            city_m = _CITY_RE.search(query)
            city = city_m.group(0) if city_m else "Shanghai"
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10, verify=False) as c:
                    r = await c.get(
                        f"https://wttr.in/{city}?format=j1&lang=zh",
                        headers={"User-Agent": "curl/7.0"},
                    )
                    d = r.json()
                    cur = d["current_condition"][0]
                    today = d["weather"][0]
                    desc = cur.get("lang_zh", [{}])[0].get("value") or cur.get("weatherDesc", [{}])[0].get("value", "")
                    summary = (
                        f"【{city} 当前天气】\n"
                        f"天气：{desc}\n"
                        f"气温：{cur['temp_C']}°C（体感 {cur['FeelsLikeC']}°C）\n"
                        f"湿度：{cur['humidity']}%  风速：{cur['windspeedKmph']} km/h\n"
                        f"今日：最低 {today['mintempC']}°C / 最高 {today['maxtempC']}°C\n"
                        f"数据来源：wttr.in"
                    )
                    return {"results": [{"type": "weather", "text": summary}], "query": query}
            except Exception as e:
                pass  # fall through to general search

        # ── General search via ddgs ───────────────────────────────────────────
        try:
            from ddgs import DDGS
            loop = __import__("asyncio").get_event_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=num)),
            )
            if raw:
                results = [{"title": r.get("title", ""), "snippet": r.get("body", ""),
                            "url": r.get("href", "")} for r in raw]
                return {"results": results, "query": query}
        except Exception:
            pass

        # ── Last resort: DuckDuckGo HTML ──────────────────────────────────────
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15, verify=False) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                )
                titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                html_results = []
                for t, s in zip(titles[:num], snippets[:num]):
                    t_clean = re.sub(r"<[^>]+>", "", t).strip()
                    s_clean = re.sub(r"<[^>]+>", "", s).strip()
                    if t_clean or s_clean:
                        html_results.append({"title": t_clean, "snippet": s_clean})
                if html_results:
                    return {"results": html_results, "query": query}
        except Exception as e:
            return {"error": str(e), "query": query}

        return {"results": [{"text": "未找到相关结果，建议换一个关键词"}], "query": query}
