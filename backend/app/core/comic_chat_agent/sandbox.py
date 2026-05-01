"""
P7 Sandbox —— Agent 工具执行安全隔离层。

职责：
 1. 定义工具风险等级（L0-L4）。
 2. 定义 SandboxPolicy（路径 / 命令 / 网络 allowlist/denylist）。
 3. 在 execute_tool 之前做前置检查，返回 SandboxDecision。
 4. 高风险操作直接 block，中风险操作标记需审批。
"""
from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from app.config import settings


# ═══════════════════ 风险等级 ═══════════════════

class RiskLevel(IntEnum):
    L0 = 0  # 只读安全：list_dir / read_file（限定目录）
    L1 = 1  # 创作类：generate_image / text_to_speech
    L2 = 2  # 文件写入 / HTTP：write_file / edit_file / http_request
    L3 = 3  # 命令执行：bash / python_exec
    L4 = 4  # 禁止级：rm -rf / 读取 .env / 外发密钥


TOOL_RISK_LEVELS: dict[str, RiskLevel] = {
    # L0
    "list_dir": RiskLevel.L0,
    "find_files": RiskLevel.L0,
    "grep_search": RiskLevel.L0,
    "read_file": RiskLevel.L0,
    "web_search": RiskLevel.L0,
    # L1
    "generate_image": RiskLevel.L1,
    "generate_image_with_face": RiskLevel.L1,
    "edit_image": RiskLevel.L1,
    "image_to_video": RiskLevel.L1,
    "text_to_video": RiskLevel.L1,
    "upscale_image": RiskLevel.L1,
    "text_to_speech": RiskLevel.L1,
    "merge_media": RiskLevel.L1,
    "add_subtitle": RiskLevel.L1,
    "jimeng_generate_image": RiskLevel.L1,
    "jimeng_reference_image": RiskLevel.L1,
    "jimeng_edit_image": RiskLevel.L1,
    "jimeng_upscale_image": RiskLevel.L1,
    "jimeng_generate_video": RiskLevel.L1,
    "jimeng_motion_mimic": RiskLevel.L1,
    # L2
    "write_file": RiskLevel.L2,
    "edit_file": RiskLevel.L2,
    "http_request": RiskLevel.L2,
    "web_fetch": RiskLevel.L2,
    # L3
    "bash": RiskLevel.L3,
    "python_exec": RiskLevel.L3,
}


# ═══════════════════ SandboxPolicy ═══════════════════

def _default_allowed_read_dirs() -> list[str]:
    upload_dir = str(Path(settings.UPLOAD_DIR).resolve())
    return [
        upload_dir,
        "/tmp",
    ]


def _default_allowed_write_dirs() -> list[str]:
    agent_out = str((Path(settings.UPLOAD_DIR).resolve() / "agent_outputs"))
    return [
        agent_out,
        "/tmp/ttsapp_agent_tasks",
    ]


@dataclass
class SandboxPolicy:
    allowed_read_dirs: list[str] = field(default_factory=_default_allowed_read_dirs)
    allowed_write_dirs: list[str] = field(default_factory=_default_allowed_write_dirs)
    denied_path_patterns: list[str] = field(default_factory=lambda: [
        r"\.env$",
        r"\.env\.",
        r"/\.ssh/",
        r"/\.git/",
        r"/node_modules/",
        r"__pycache__",
    ])
    denied_filenames: list[str] = field(default_factory=lambda: [
        ".env", ".env.local", ".env.production",
        "id_rsa", "id_ed25519", "authorized_keys",
    ])
    denied_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=/dev/zero",
        "dd if=/dev/random",
        ":(){:|:&};:",
        "chmod -R 777 /",
        "curl|sh", "curl|bash",
        "wget|sh", "wget|bash",
    ])
    denied_command_patterns: list[str] = field(default_factory=lambda: [
        r"curl\s+.*\|\s*(ba)?sh",
        r"wget\s+.*\|\s*(ba)?sh",
        r"rm\s+-[rf]*\s+/($|\s)",
        r">\s*/etc/",
        r"cat\s+.*\.env",
        r"echo\s+.*>\s*/etc/",
    ])
    denied_hosts: list[str] = field(default_factory=lambda: [
        "169.254.169.254",
        "metadata.google.internal",
    ])
    denied_network_cidrs: list[str] = field(default_factory=lambda: [
        "169.254.0.0/16",
        "127.0.0.0/8",
    ])
    allowed_network_cidrs: list[str] = field(default_factory=lambda: [
        "0.0.0.0/0",  # 默认允许公网，denied 优先
    ])
    timeout_seconds: int = 60
    max_output_chars: int = 8192


# ═══════════════════ SandboxDecision ═══════════════════

@dataclass
class SandboxDecision:
    allowed: bool
    risk_level: RiskLevel
    check_type: str = ""  # path / command / network / env / risk
    reason: str = ""


# ═══════════════════ SandboxChecker ═══════════════════

_DEFAULT_POLICY: SandboxPolicy | None = None


def _get_policy() -> SandboxPolicy:
    global _DEFAULT_POLICY
    if _DEFAULT_POLICY is None:
        _DEFAULT_POLICY = SandboxPolicy()
    return _DEFAULT_POLICY


class SandboxChecker:
    """工具执行前置安全检查器。"""

    def __init__(self, policy: SandboxPolicy | None = None):
        self.policy = policy or _get_policy()
        self._denied_path_re = [re.compile(p) for p in self.policy.denied_path_patterns]
        self._denied_cmd_re = [re.compile(p) for p in self.policy.denied_command_patterns]

    # ── 路径检查 ──

    def check_read_path(self, path: str) -> SandboxDecision:
        resolved = str(Path(path).resolve())
        if self._is_denied_path(resolved):
            return SandboxDecision(
                allowed=False, risk_level=RiskLevel.L4,
                check_type="path",
                reason=f"读取被拒绝：路径命中安全黑名单 {path}",
            )
        return SandboxDecision(allowed=True, risk_level=RiskLevel.L0, check_type="path")

    def check_write_path(self, path: str) -> SandboxDecision:
        resolved = str(Path(path).resolve())
        if self._is_denied_path(resolved):
            return SandboxDecision(
                allowed=False, risk_level=RiskLevel.L4,
                check_type="path",
                reason=f"写入被拒绝：路径命中安全黑名单 {path}",
            )
        if not self._is_in_allowed_dirs(resolved, self.policy.allowed_write_dirs):
            return SandboxDecision(
                allowed=False, risk_level=RiskLevel.L2,
                check_type="path",
                reason=f"写入被拒绝：不在允许写入目录 {path}",
            )
        return SandboxDecision(allowed=True, risk_level=RiskLevel.L2, check_type="path")

    # ── 命令检查 ──

    def check_command(self, command: str) -> SandboxDecision:
        cmd_lower = command.lower().strip()
        for pat in self.policy.denied_commands:
            if pat.lower() in cmd_lower:
                return SandboxDecision(
                    allowed=False, risk_level=RiskLevel.L4,
                    check_type="command",
                    reason=f"命令被拒绝：包含危险片段 '{pat}'",
                )
        for rx in self._denied_cmd_re:
            if rx.search(cmd_lower):
                return SandboxDecision(
                    allowed=False, risk_level=RiskLevel.L4,
                    check_type="command",
                    reason=f"命令被拒绝：命中危险模式 '{rx.pattern}'",
                )
        return SandboxDecision(allowed=True, risk_level=RiskLevel.L3, check_type="command")

    # ── 网络检查 ──

    def check_url(self, url: str) -> SandboxDecision:
        try:
            parsed = urlparse(url)
            host = parsed.hostname or ""
        except Exception:
            return SandboxDecision(
                allowed=False, risk_level=RiskLevel.L2,
                check_type="network",
                reason=f"URL 解析失败：{url}",
            )
        if host in self.policy.denied_hosts:
            return SandboxDecision(
                allowed=False, risk_level=RiskLevel.L4,
                check_type="network",
                reason=f"网络请求被拒绝：目标主机 {host} 在黑名单中",
            )
        try:
            ip = ipaddress.ip_address(host)
            for cidr in self.policy.denied_network_cidrs:
                if ip in ipaddress.ip_network(cidr, strict=False):
                    return SandboxDecision(
                        allowed=False, risk_level=RiskLevel.L4,
                        check_type="network",
                        reason=f"网络请求被拒绝：{host} 在禁止网段 {cidr}",
                    )
        except ValueError:
            pass  # 非 IP，是域名，放行
        return SandboxDecision(allowed=True, risk_level=RiskLevel.L2, check_type="network")

    # ── Python 代码检查 ──

    def check_python_code(self, code: str) -> SandboxDecision:
        dangerous_patterns = [
            (r"os\.environ", "禁止访问环境变量"),
            (r"subprocess\.(run|Popen|call)", "禁止启动子进程"),
            (r"__import__\s*\(\s*['\"]os['\"]", "禁止动态导入 os"),
            (r"open\s*\(.*\.env", "禁止读取 .env 文件"),
            (r"shutil\.rmtree\s*\(\s*['\"/]", "禁止递归删除根目录"),
        ]
        for pat, msg in dangerous_patterns:
            if re.search(pat, code):
                return SandboxDecision(
                    allowed=False, risk_level=RiskLevel.L4,
                    check_type="command",
                    reason=f"Python 代码被拒绝：{msg}",
                )
        return SandboxDecision(allowed=True, risk_level=RiskLevel.L3, check_type="command")

    # ── 统一入口 ──

    def check_tool(self, tool_name: str, params: dict[str, Any]) -> SandboxDecision:
        risk = TOOL_RISK_LEVELS.get(tool_name, RiskLevel.L2)

        # L0/L1 的路径型工具仍需检查 denied paths
        if tool_name == "read_file":
            path = params.get("path", "")
            if path:
                d = self.check_read_path(path)
                if not d.allowed:
                    return d

        if tool_name in ("write_file", "edit_file"):
            path = params.get("path", "")
            if path:
                d = self.check_write_path(path)
                if not d.allowed:
                    return d

        if tool_name == "bash":
            cmd = params.get("command", "")
            if cmd:
                d = self.check_command(cmd)
                if not d.allowed:
                    return d

        if tool_name == "python_exec":
            code = params.get("code") or params.get("script") or ""
            if code:
                d = self.check_python_code(code)
                if not d.allowed:
                    return d

        if tool_name in ("http_request", "web_fetch"):
            url = params.get("url", "")
            if url:
                d = self.check_url(url)
                if not d.allowed:
                    return d

        return SandboxDecision(allowed=True, risk_level=risk, check_type="risk")

    # ── 内部工具 ──

    def _is_denied_path(self, resolved: str) -> bool:
        basename = os.path.basename(resolved)
        if basename in self.policy.denied_filenames:
            return True
        for rx in self._denied_path_re:
            if rx.search(resolved):
                return True
        return False

    def _is_in_allowed_dirs(self, resolved: str, allowed: list[str]) -> bool:
        for d in allowed:
            if resolved.startswith(d):
                return True
        return False
