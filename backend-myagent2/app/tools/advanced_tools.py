"""Advanced tools — git, notebook, zip, image, pdf, env_info."""
from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .base import BaseTool
from .builtin import _expose_file, _OUTPUTS_DIR


# ── Git ───────────────────────────────────────────────────────────────────────

class GitTool(BaseTool):
    name = "git"
    description = "执行 Git 操作：diff / log / status / add / commit / push / pull / branch"
    category = "vcs"
    risk_level = "medium"

    _SAFE_OPS = {"diff", "log", "status", "show", "branch", "tag", "stash", "remote"}
    _WRITE_OPS = {"add", "commit", "push", "pull", "merge", "rebase", "checkout", "reset", "init"}

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Git 子命令：diff / log / status / add / commit / push / pull / branch / checkout 等",
                },
                "args": {
                    "type": "string",
                    "description": "传给 git 子命令的额外参数（可选）",
                    "default": "",
                },
                "cwd": {
                    "type": "string",
                    "description": "仓库路径，默认当前目录",
                    "default": ".",
                },
            },
            "required": ["operation"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        op = arguments["operation"].strip().lower()
        args = arguments.get("args", "").strip()
        cwd = arguments.get("cwd", ".") or "."
        cmd = f"git {op} {args}".strip()
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), 30)
            return {
                "stdout": stdout.decode(errors="replace")[:50_000],
                "stderr": stderr.decode(errors="replace")[:10_000],
                "code": proc.returncode,
                "command": cmd,
            }
        except asyncio.TimeoutError:
            return {"error": "git command timed out", "code": -1}
        except Exception as e:
            return {"error": str(e), "code": -1}


# ── Notebook Read ─────────────────────────────────────────────────────────────

class NotebookReadTool(BaseTool):
    name = "notebook_read"
    description = "读取 Jupyter Notebook (.ipynb) 所有 cell 内容和执行结果"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Notebook 文件路径 (.ipynb)"},
                "include_outputs": {
                    "type": "boolean",
                    "description": "是否包含执行输出（默认 true）",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        include_outputs = arguments.get("include_outputs", True)
        try:
            with open(path, "r", encoding="utf-8") as f:
                nb = json.load(f)
        except Exception as e:
            return {"error": str(e)}

        cells = []
        for idx, cell in enumerate(nb.get("cells", [])):
            source = "".join(cell.get("source", []))
            entry: dict[str, Any] = {
                "index": idx,
                "type": cell.get("cell_type", ""),
                "source": source,
            }
            if include_outputs and cell.get("cell_type") == "code":
                outputs = []
                for out in cell.get("outputs", []):
                    otype = out.get("output_type", "")
                    if otype in ("stream",):
                        outputs.append({"type": otype, "text": "".join(out.get("text", []))})
                    elif otype in ("execute_result", "display_data"):
                        data = out.get("data", {})
                        text = "".join(data.get("text/plain", []))
                        outputs.append({"type": otype, "text": text})
                    elif otype == "error":
                        outputs.append({"type": "error", "ename": out.get("ename", ""), "evalue": out.get("evalue", "")})
                entry["outputs"] = outputs
                entry["execution_count"] = cell.get("execution_count")
            cells.append(entry)

        return {
            "path": path,
            "kernel": nb.get("metadata", {}).get("kernelspec", {}).get("name", ""),
            "cell_count": len(cells),
            "cells": cells,
        }


# ── Notebook Edit ─────────────────────────────────────────────────────────────

class NotebookEditTool(BaseTool):
    name = "notebook_edit"
    description = "编辑 Jupyter Notebook 指定 cell 的内容，或插入/追加新 cell"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Notebook 文件路径 (.ipynb)"},
                "cell_index": {
                    "type": "integer",
                    "description": "要编辑的 cell 索引（0-indexed）；-1 表示在末尾追加新 cell",
                },
                "new_source": {"type": "string", "description": "新的 cell 代码内容"},
                "cell_type": {
                    "type": "string",
                    "description": "cell 类型：code / markdown（追加时有效，默认 code）",
                    "default": "code",
                },
            },
            "required": ["path", "cell_index", "new_source"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        cell_index = int(arguments["cell_index"])
        new_source = arguments["new_source"]
        cell_type = arguments.get("cell_type", "code")

        try:
            with open(path, "r", encoding="utf-8") as f:
                nb = json.load(f)
        except Exception as e:
            return {"error": f"Failed to read notebook: {e}"}

        cells = nb.get("cells", [])
        source_lines = [line if line.endswith("\n") else line + "\n" for line in new_source.splitlines()]
        # Fix last line: no trailing newline
        if source_lines:
            source_lines[-1] = source_lines[-1].rstrip("\n")

        if cell_index == -1:
            new_cell: dict[str, Any] = {
                "cell_type": cell_type,
                "metadata": {},
                "source": source_lines,
            }
            if cell_type == "code":
                new_cell["execution_count"] = None
                new_cell["outputs"] = []
            cells.append(new_cell)
            action = "appended"
        else:
            if cell_index < 0 or cell_index >= len(cells):
                return {"error": f"cell_index {cell_index} out of range (0..{len(cells)-1})"}
            cells[cell_index]["source"] = source_lines
            if cell_type:
                cells[cell_index]["cell_type"] = cell_type
            # Clear stale outputs on code cell edit
            if cells[cell_index].get("cell_type") == "code":
                cells[cell_index]["outputs"] = []
                cells[cell_index]["execution_count"] = None
            action = f"edited cell[{cell_index}]"

        nb["cells"] = cells
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(nb, f, ensure_ascii=False, indent=1)
        except Exception as e:
            return {"error": f"Failed to write notebook: {e}"}

        return {"success": True, "action": action, "cell_count": len(cells)}


# ── Zip Files ─────────────────────────────────────────────────────────────────

class ZipFilesTool(BaseTool):
    name = "zip_files"
    description = "将多个文件/目录打包为 ZIP，返回下载链接"
    category = "filesystem"
    risk_level = "medium"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要打包的文件或目录列表",
                },
                "output": {
                    "type": "string",
                    "description": "输出 ZIP 路径（可选，不填自动生成到 /tmp）",
                    "default": "",
                },
            },
            "required": ["paths"],
        }

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        paths = arguments["paths"]
        output = arguments.get("output", "").strip()
        if not output:
            output = f"/tmp/archive_{uuid.uuid4().hex[:8]}.zip"

        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    p = os.path.expanduser(p)
                    if os.path.isdir(p):
                        for root, _, files in os.walk(p):
                            for fname in files:
                                full = os.path.join(root, fname)
                                arcname = os.path.relpath(full, os.path.dirname(p))
                                zf.write(full, arcname)
                    elif os.path.isfile(p):
                        zf.write(p, os.path.basename(p))
                    else:
                        return {"error": f"Path not found: {p}"}

            url = _expose_file(output)
            size = os.path.getsize(output)
            return {
                "success": True,
                "output": output,
                "size_bytes": size,
                "file_urls": [{"url": url, "name": Path(output).name, "type": "document"}] if url else [],
            }
        except Exception as e:
            return {"error": str(e)}


# ── Image Read ────────────────────────────────────────────────────────────────

class ImageReadTool(BaseTool):
    name = "image_read"
    description = "读取图片文件，返回 Base64 编码（用于多模态 LLM 输入）"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "图片文件路径"},
                "max_size_kb": {
                    "type": "integer",
                    "description": "最大文件大小限制（KB），超过则拒绝，默认 4096KB",
                    "default": 4096,
                },
            },
            "required": ["path"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        max_kb = arguments.get("max_size_kb", 4096)
        try:
            size = os.path.getsize(path)
            if size > max_kb * 1024:
                return {"error": f"File too large: {size // 1024}KB > {max_kb}KB"}
            mime, _ = mimetypes.guess_type(path)
            mime = mime or "image/png"
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return {
                "data_url": f"data:{mime};base64,{data}",
                "mime_type": mime,
                "size_bytes": size,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


# ── PDF Read ──────────────────────────────────────────────────────────────────

class PdfReadTool(BaseTool):
    name = "pdf_read"
    description = "提取 PDF 文件文字内容（逐页返回）"
    category = "filesystem"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "PDF 文件路径"},
                "max_pages": {
                    "type": "integer",
                    "description": "最多读取页数，默认 20",
                    "default": 20,
                },
            },
            "required": ["path"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = arguments["path"]
        max_pages = arguments.get("max_pages", 20)

        # Try pypdf first
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(path)
            pages = []
            for i, page in enumerate(reader.pages[:max_pages]):
                text = page.extract_text() or ""
                pages.append({"page": i + 1, "text": text[:10_000]})
            return {"path": path, "total_pages": len(reader.pages), "pages": pages}
        except ImportError:
            pass

        # Fallback: pdftotext (system tool)
        try:
            proc = await asyncio.create_subprocess_shell(
                f'pdftotext -l {max_pages} "{path}" -',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), 30)
            text = stdout.decode(errors="replace")
            return {"path": path, "text": text[:100_000], "method": "pdftotext"}
        except Exception:
            pass

        return {"error": "No PDF reader available. Install: pip install pypdf"}


# ── Env Info ──────────────────────────────────────────────────────────────────

class EnvInfoTool(BaseTool):
    name = "env_info"
    description = "获取运行环境信息：OS、Python 版本、CPU/内存、已安装包"
    category = "system"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "include_packages": {
                    "type": "boolean",
                    "description": "是否列出已安装 Python 包（默认 false）",
                    "default": False,
                },
            },
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import platform
        import shutil

        info: dict[str, Any] = {
            "os": platform.platform(),
            "python": sys.version,
            "python_executable": sys.executable,
            "cwd": os.getcwd(),
        }

        # CPU / memory via psutil (optional)
        try:
            import psutil  # type: ignore
            info["cpu_count"] = psutil.cpu_count()
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = round(mem.total / 1024 ** 3, 1)
            info["memory_available_gb"] = round(mem.available / 1024 ** 3, 1)
        except ImportError:
            pass

        # Disk space
        try:
            usage = shutil.disk_usage(os.getcwd())
            info["disk_free_gb"] = round(usage.free / 1024 ** 3, 1)
        except Exception:
            pass

        # Installed packages
        if arguments.get("include_packages", False):
            try:
                proc = await asyncio.create_subprocess_shell(
                    f'"{sys.executable}" -m pip list --format=columns 2>/dev/null | head -80',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), 15)
                info["packages"] = stdout.decode(errors="replace")
            except Exception:
                pass

        return info


# ── Process List ─────────────────────────────────────────────────────────────

class ProcessListTool(BaseTool):
    name = "process_list"
    description = "列出当前运行的进程（支持按名称过滤）"
    category = "system"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "按进程名过滤（可选，支持部分匹配）",
                    "default": "",
                },
                "limit": {
                    "type": "integer",
                    "description": "最多返回条数，默认 50",
                    "default": 50,
                },
            },
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        filt = (arguments.get("filter") or "").lower()
        limit = int(arguments.get("limit", 50))

        try:
            import psutil  # type: ignore
            procs = []
            for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_info"]):
                try:
                    info = p.info
                    name = (info.get("name") or "").lower()
                    if filt and filt not in name:
                        continue
                    mem_mb = round((info["memory_info"].rss if info.get("memory_info") else 0) / 1024 ** 2, 1)
                    procs.append({
                        "pid": info["pid"],
                        "name": info["name"],
                        "status": info["status"],
                        "cpu%": info["cpu_percent"],
                        "mem_mb": mem_mb,
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return {"processes": procs[:limit], "total": len(procs)}
        except ImportError:
            pass

        # fallback: ps aux
        cmd = f"ps aux | grep -i '{filt}'" if filt else "ps aux"
        cmd += f" | head -{limit + 1}"
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), 10)
        return {"output": stdout.decode(errors="replace")}


# ── Multi Bash ────────────────────────────────────────────────────────────────

class MultiBashTool(BaseTool):
    name = "multi_bash"
    description = "并发执行多条 Shell 命令，所有命令同时启动，返回各自结果"
    category = "shell"
    risk_level = "high"

    BLOCKED_PATTERNS = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:"]

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要并发执行的命令列表",
                },
                "timeout": {
                    "type": "integer",
                    "description": "每条命令超时秒数，默认 30",
                    "default": 30,
                },
                "working_dir": {
                    "type": "string",
                    "description": "工作目录（所有命令共用）",
                    "default": "",
                },
            },
            "required": ["commands"],
        }

    async def _run_one(self, cmd: str, timeout: int, cwd: str | None) -> dict[str, Any]:
        for pat in self.BLOCKED_PATTERNS:
            if pat in cmd:
                return {"command": cmd, "error": f"Blocked: {pat}", "code": -1}
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or None,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
            return {
                "command": cmd,
                "stdout": stdout.decode(errors="replace")[:20_000],
                "stderr": stderr.decode(errors="replace")[:5_000],
                "code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"command": cmd, "error": f"timed out after {timeout}s", "code": -1}
        except Exception as e:
            return {"command": cmd, "error": str(e), "code": -1}

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        commands = arguments["commands"]
        timeout = int(arguments.get("timeout", 30))
        cwd = arguments.get("working_dir", "") or None
        results = await asyncio.gather(*[self._run_one(c, timeout, cwd) for c in commands])
        return {"results": list(results)}


# ── Export ────────────────────────────────────────────────────────────────────

ALL_ADVANCED_TOOLS = [
    GitTool,
    NotebookReadTool,
    NotebookEditTool,
    ZipFilesTool,
    ImageReadTool,
    PdfReadTool,
    EnvInfoTool,
    ProcessListTool,
    MultiBashTool,
]
