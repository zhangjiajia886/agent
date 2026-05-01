from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_ROOT = Path(os.getenv("USER_WORKSPACE_ROOT", "/tmp/myagent_workspaces"))


def get_user_workspace(username: str) -> Path:
    """Return (and create) the persistent workspace root for a user."""
    ws = WORKSPACE_ROOT / username
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def get_session_workspace(username: str, session_id: str) -> Path:
    """Return (and create) the per-session subdirectory inside the user workspace."""
    ws = get_user_workspace(username) / "sessions" / session_id
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def get_upload_dir(username: str) -> Path:
    """Return (and create) the uploads directory for a user."""
    d = get_user_workspace(username) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def workspace_system_prompt_appendix(username: str, session_id: str) -> str:
    """Inject workspace path into system prompt so the LLM writes files to the right place."""
    ws = get_session_workspace(username, session_id)
    return (
        f"\n\n## 用户工作区\n"
        f"当前用户: {username}\n"
        f"工作目录: {ws}\n"
        f"所有临时文件、脚本、图表、报告必须写入此目录（而非 /tmp/ 根目录），"
        f"bash 命令也在此目录执行。"
    )
