from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Any

from ..db.database import get_db
from ..llm.client import LLMClient, LLMStreamChunk
from ..tools.registry import ToolRegistry
from ..core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """你是一个智能助手，能够帮助用户完成各种任务。
你可以使用工具来执行操作，例如执行命令、读写文件、搜索内容、发送HTTP请求等。
在使用工具时，请确认操作意图后再执行。回答请使用用户的语言。"""

DIAGRAM_INSTRUCTIONS = """

【代码执行规范 — 严格遵守】
当需要执行 Python 或 Shell 脚本时：
  1. 优先用 write_file 将代码写入 /tmp/<任务名>.py 或 /tmp/<任务名>.sh
  2. 再用 bash 执行：python3 /tmp/<任务名>.py 或 bash /tmp/<任务名>.sh
  3. 不要将大段代码直接贴到聊天回复里，文件路径简洁说明即可
  4. 脚本应尽量生成图片（PNG）或结构化数据（CSV），优先用图片展示结果
  5. 生成图片后系统自动显示，无需手写 ![](路径) Markdown 引用

【可视化优先策略】
  - 有数据结果 → 优先用 Python matplotlib / seaborn 生成 PNG
  - 有表格数据 → 优先用 ECharts HTML 代码块渲染交互图表
  - 有目录/流程 → 用 Mermaid 代码块渲染流程图
  - 纯文字表格作为最后兜底

【图表渲染规则 — 严格遵守】
画图时调用 draw_diagram 工具，或直接输出代码块，前端自动渲染。

Mermaid 严格规则（违反会报错）：
  ✅ 正确：flowchart TD / graph LR / sequenceDiagram / erDiagram
  ✅ 节点标签：A["中文"]  B["English"]  （中文必须加双引号）
  ✅ 边标签：A -->|"标签"| B
  ❌ 禁止：节点内写 CSS，如 A[fill:#fff] A[color:red,stroke:#333]
  ❌ 禁止：classDef / class 语句
  ❌ 禁止：style 语句内写 CSS 属性
  ❌ 禁止：调用工具名为 mermaid/plantuml（它们是输出格式，不是工具）

安全模板：
```mermaid
flowchart TD
    A["开始"] --> B{"判断条件"}
    B -->|"是"| C["执行操作"]
    B -->|"否"| D["结束"]
```

【生成文件展示规则】
用工具（python_exec / bash）生成图片或文件后：
  ✅ 直接用文字描述图表内容即可，系统自动将文件展示在聊天界面
  ❌ 禁止在文本中写 ![图片名](路径) 这样的 Markdown 图片引用
  ❌ 禁止引用本地路径（如 sine_cosine.png、/tmp/chart.png）
  原因：前端通过 file_urls 机制自动渲染，手写引用会生成无效 URL

【交互式 HTML 应用生成】
如需生成可交互图表、计算器、小工具，直接输出完整的 ```html 代码块，前端用沙箱渲染：
  ✅ 通过 CDN 引入库（ECharts / Chart.js / D3.js 等）
  ✅ 宽度使用 100%，高度建议 300-400px
  ✅ 代码必须完整，能在独立 iframe 中运行
  ❌ 禁止访问 localStorage / sessionStorage / Cookie / window.parent
  ❌ 禁止 fetch 外部 API（沙箱内受限）

HTML 图表模板：
```html
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
</head><body style="margin:0">
<div id="c" style="width:100%;height:350px"></div>
<script>
  echarts.init(document.getElementById('c')).setOption({
    xAxis:{data:["A","B","C"]}, yAxis:{}, series:[{type:"bar",data:[10,20,15]}]
  });
</script></body></html>
```"""

REACT_TOOL_BLOCK_RE = re.compile(
    r"(?:```[^\n]*\n\s*)?<tool_call>\s*(\{.*?\})\s*</tool_call>\s*(?:```)?",
    re.DOTALL | re.IGNORECASE,
)
_THINKING_RE = re.compile(r"<(thinking|think)>.*?</(thinking|think)>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(text: str) -> str:
    """Strip <thinking>/<think> blocks before injecting into LLM context."""
    return _THINKING_RE.sub("", text).strip()

MAX_TOOL_ROUNDS = 20
MAX_HISTORY_MESSAGES = 50

# ── Human-in-the-loop 确认机制 ──
# 只读/查询类工具无需确认，直接执行；高危工具（写文件、执行命令）仍需确认。
CONFIRM_SKIP_TOOLS: set[str] = {
    "web_search", "web_fetch", "read_file", "grep_search",
    "find_files", "list_dir", "mysql_query",
}
# key = tool_call_id → asyncio.Event（后端暂停，等待前端 /confirm 回调）
_pending_confirms: dict[str, asyncio.Event] = {}
# key = tool_call_id → "allow" | "skip" | "cancel"
_confirm_actions: dict[str, str] = {}

# 单次 agent run 内每个工具最多可被调用的次数（防止无限循环）
# 0 或 key 不存在 = 不限制
MAX_TOOL_CALLS_PER_TOOL: dict[str, int] = {
    "python_exec": 3,
    "bash":        5,
    "multi_bash":  3,
}

DIRECT_TOOL_COMMANDS: dict[str, str] = {
    "bash": "bash",
    "shell": "bash",
    "sh": "bash",
    "python": "python_exec",
    "py": "python_exec",
    "search": "web_search",
    "搜索": "web_search",
    "联网": "web_search",
    "http": "http_request",
    "fetch": "http_request",
    "curl": "http_request",
    "read": "read_file",
    "cat": "read_file",
}

REACT_CALL_INSTRUCTION = """
## 工具调用
如需使用工具，在回复中插入：
<tool_call>{"name": "工具名", "arguments": {...}}</tool_call>
⚠️ 生成 </tool_call> 后立即停止，不要预测或输出工具结果，等待系统注入真实结果后再继续。"""


# ── P0：工具结果压缩 ──────────────────────────────────────────────────────────
def _compact_tool_result(tool_name: str, result: dict) -> str:
    """将工具结果压缩为最小必要信息，注入 context 时节省 ~90% token。"""
    if "error" in result:
        return f"[{tool_name}] ❌ 错误: {str(result['error'])[:300]}"

    parts = [f"[{tool_name}] ✓"]

    stdout = result.get("stdout", "").strip()
    if stdout:
        # 只保留前 400 字符；关键数据已写 /tmp，LLM 无需完整 stdout
        parts.append(f"输出:\n{stdout[:400]}" + ("..." if len(stdout) > 400 else ""))

    stderr = result.get("stderr", "").strip()
    if stderr:
        parts.append(f"stderr: {stderr[:200]}" + ("..." if len(stderr) > 200 else ""))

    if result.get("file_urls"):
        urls = [f["url"] for f in result["file_urls"]]
        parts.append(f"生成文件: {urls}")

    # 数据库工具返回 rows 结构（mysql_query / mysql_schema），需单独序列化
    if "rows" in result and not stdout:
        rows = result["rows"]
        count = result.get("count", len(rows))
        rows_str = json.dumps(rows, ensure_ascii=False, default=str)
        parts.append(f"行数: {count}\n{rows_str[:3000]}" + ("..." if len(rows_str) > 3000 else ""))
    elif "results" in result and not stdout:
        # multi-statement batch from mysql_query
        for sub in result["results"]:
            if "rows" in sub:
                rows_str = json.dumps(sub["rows"], ensure_ascii=False, default=str)
                count = sub.get("count", len(sub["rows"]))
                parts.append(f"SQL: {sub['sql']}\n行数: {count}\n{rows_str[:1500]}" + ("..." if len(rows_str) > 1500 else ""))
            else:
                parts.append(f"SQL: {sub['sql']}\n影响行数: {sub.get('affected_rows', 0)}")
    elif result.get("affected_rows") is not None and not stdout:
        parts.append(f"影响行数: {result['affected_rows']}")

    # 兜底：没有任何输出
    if len(parts) == 1:
        code = result.get("code", 0)
        parts.append(f"退出码: {code}")

    return "\n".join(parts)


# ── P1：Token 估算 + 历史压实 ─────────────────────────────────────────────────
_CHARS_PER_TOKEN = 2.5  # 中英混合保守估算

def _estimate_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        c = m.get("content") or ""
        total += int(len(str(c)) / _CHARS_PER_TOKEN)
    return total


def _compact_history_simple(messages: list[dict]) -> list[dict]:
    """
    简单规则压实：保留 system + 最近 6 条，将中间消息的工具结果进一步截断。
    不调用 LLM，纯规则，零延迟。
    """
    if len(messages) <= 8:  # system + 7 条以内无需压实
        return messages

    system_msg = messages[0]
    recent = messages[-6:]
    middle = messages[1:-6]

    compacted_middle: list[dict] = []
    for m in middle:
        content = m.get("content") or ""
        # 工具结果消息（以 [ 开头）只保留前 150 字符
        if isinstance(content, str) and content.startswith("[") and len(content) > 200:
            content = content[:150] + "…[已压缩]"
        compacted_middle.append({**m, "content": content})

    return [system_msg] + compacted_middle + recent


TOKEN_COMPACT_THRESHOLD = 10000  # 超过此估算 token 数时触发压实


def _build_preview(tool_name: str, args: dict) -> str:
    if tool_name in ("bash", "multi_bash"):
        return f"命令：{args.get('command') or args.get('commands', [])}"
    if tool_name == "python_exec":
        code = args.get("code") or args.get("script") or args.get("cmd") or ""
        lines = code.strip().splitlines()
        preview = "\n".join(lines[:20])
        return preview + (f"\n... (共 {len(lines)} 行)" if len(lines) > 20 else "")
    if tool_name == "write_file":
        path = args.get("path", "")
        lines = args.get("content", "").splitlines()
        preview = f"写入文件：{path}\n\n" + "\n".join(f"+ {l}" for l in lines[:20])
        return preview + (f"\n... (+{len(lines) - 20} 行)" if len(lines) > 20 else "")
    if tool_name == "edit_file":
        path = args.get("path", "")
        return (f"编辑文件：{path}\n"
                f"--- 替换前\n{args.get('old_string', '')[:300]}\n"
                f"+++ 替换后\n{args.get('new_string', '')[:300]}")
    return str(args)[:500]


class AgentLoop:
    """
    Single user-message → Agent reasoning loop.

    Slash command dispatch priority:
    1. /bash /python /search /http  → direct tool execution (no LLM)
    2. /skillName                   → skill system prompt + tool filtering
    3. Normal message               → LLM with ReAct tool support
    """

    def __init__(self, llm: LLMClient, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.settings = get_settings()

    async def run(
        self,
        session_id: str,
        user_content: str,
        model_override: str = "",
        system_prompt_override: str = "",
        allowed_tools: list[str] | None = None,
        history_override: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        enable_thinking: bool = False,
    ) -> AsyncIterator[dict]:
        model = model_override or self.settings.llm_default_model
        start_time = time.time()

        # ── 1. Direct tool command ──
        if user_content.startswith("/"):
            parts = user_content.split(None, 1)
            cmd = parts[0][1:].lower()
            args_str = parts[1] if len(parts) > 1 else ""
            if cmd in DIRECT_TOOL_COMMANDS:
                async for event in self._run_direct_tool(cmd, args_str, start_time):
                    yield event
                return

        # ── 2. Skill slash command ──
        skill = None
        actual_content = user_content
        if user_content.startswith("/"):
            skill, actual_content = await self._check_skill_command(user_content)

        # ── 3. Build system prompt ──
        system_prompt = system_prompt_override or DEFAULT_SYSTEM_PROMPT
        if skill:
            system_prompt = skill["content"]
            if skill.get("argument_hint"):
                system_prompt += f"\n\nArgument hint: {skill['argument_hint']}"
        # Always inject diagram/image rendering instructions
        system_prompt = system_prompt.rstrip() + DIAGRAM_INSTRUCTIONS

        # Always inject real-time clock so the model knows today's date
        now = datetime.now()
        weekdays = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
        date_line = (
            f"\n\n【当前时间】{now.strftime('%Y年%m月%d日')} "
            f"{weekdays[now.weekday()]} {now.strftime('%H:%M')}（北京时间）"
        )
        system_prompt = system_prompt.rstrip() + date_line

        tool_schemas = self._get_tool_schemas(skill, allowed_tools)
        react_prompt = self._build_react_prompt(tool_schemas)
        if react_prompt:
            system_prompt = system_prompt.rstrip() + react_prompt

        # ── 4. Load history & assemble messages ──
        history = history_override if history_override is not None else await self._load_history(session_id)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": actual_content})

        # ── 5. Agent loop ──
        total_input_tokens = 0
        total_output_tokens = 0
        all_tool_calls: list[dict] = []
        tool_call_counts: dict[str, int] = {}  # 当前 run 内每个工具的调用计数

        _sid = session_id[:12] if session_id else "no-session"
        _init_tokens = _estimate_tokens(messages)
        logger.info(
            f"[AGENT START] sid={_sid} model={model} "
            f"history={len(history)} est_tokens={_init_tokens} "
            f"user=\"{actual_content[:60].replace(chr(10),' ')}\""
        )

        for round_num in range(MAX_TOOL_ROUNDS + 1):  # +1 for forced-summary round
            round_text = ""
            round_tool_calls: list[dict] = []

            # P1：每轮开始前估算 token，超阈值则压实历史
            est = _estimate_tokens(messages)
            if est > TOKEN_COMPACT_THRESHOLD:
                messages = _compact_history_simple(messages)
                est_after = _estimate_tokens(messages)
                logger.info(f"[COMPRESS] sid={_sid} round={round_num} tokens {est}→{est_after} msgs {len(messages)+len(messages)-len(messages)}→{len(messages)}")
                est = est_after

            # P0：Token 预算感知提示（注入最后一条 system 消息末尾）
            _budget_pct = est / 32000
            if _budget_pct >= 0.75 and messages and messages[0]["role"] == "system":
                budget_hint = (
                    f"\n\n【⚠️ 上下文紧张: {est}/32000 tokens({_budget_pct:.0%})】"
                    "请立即输出最终结论，禁止再调用超过1次工具。"
                )
                if "上下文紧张" not in messages[0]["content"]:
                    messages[0] = {**messages[0], "content": messages[0]["content"] + budget_hint}
                    logger.warning(f"[BUDGET⚠] sid={_sid} round={round_num} est={est} ({_budget_pct:.0%}) 已注入紧张提示")
            elif _budget_pct >= 0.5 and messages and messages[0]["role"] == "system":
                budget_hint = f"\n\n【上下文提示: 已用{est}/32000 tokens({_budget_pct:.0%})，保持输出简洁。】"
                if "上下文提示" not in messages[0]["content"] and "上下文紧张" not in messages[0]["content"]:
                    messages[0] = {**messages[0], "content": messages[0]["content"] + budget_hint}
                    logger.info(f"[BUDGET] sid={_sid} round={round_num} est={est} ({_budget_pct:.0%}) 已注入简洁提示")

            # On the final extra round, strip tools so LLM must write final answer
            is_summary_round = round_num == MAX_TOOL_ROUNDS
            round_enable_thinking = enable_thinking if round_num == 0 else False
            if is_summary_round:
                messages.append({
                    "role": "user",
                    "content": "[系统提示] 已达到最大工具轮次，请立即根据已有信息给出完整的最终回答，不要再调用任何工具。",
                })
            logger.info(
                f"[LLM CALL] sid={_sid} round={round_num}/{MAX_TOOL_ROUNDS} "
                f"msgs={len(messages)} est_tokens={est} ({_budget_pct:.0%}) "
                f"thinking={round_enable_thinking} summary_round={is_summary_round}"
            )
            _llm_t0 = time.time()
            try:
                stream = await self.llm.chat(
                    model=model,
                    messages=messages,
                    tools=None if is_summary_round else (tool_schemas if tool_schemas else None),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    enable_thinking=round_enable_thinking,
                )
                async for chunk in stream:
                    if chunk.text:
                        round_text += chunk.text
                        yield {"type": "delta", "content": chunk.text}
                    if chunk.is_done:
                        total_input_tokens += chunk.input_tokens
                        total_output_tokens += chunk.output_tokens
                        if chunk.tool_calls:
                            round_tool_calls = chunk.tool_calls
                        _llm_ms = int((time.time() - _llm_t0) * 1000)
                        logger.info(
                            f"[LLM DONE] sid={_sid} round={round_num} "
                            f"in={chunk.input_tokens} out={chunk.output_tokens} "
                            f"latency={_llm_ms}ms text_len={len(round_text)} "
                            f"tool_calls={len(round_tool_calls)}"
                        )
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                err_msg = f"{type(e).__name__}: {e}" if str(e) else f"{type(e).__name__}: {repr(e)}"
                logger.error(f"[LLM ERROR] sid={_sid} round={round_num}: {err_msg}\n{tb}")
                # Human-readable hint for connectivity failures
                if any(k in type(e).__name__ for k in ("ConnectError", "ConnectionError", "APIConnectionError")):
                    hint = (
                        "无法连接到模型服务。"
                        "请检查网络，或在应用设置 → 模型中选择其他可用模型（如 AIPro 模型）。"
                    )
                    yield {"type": "error", "message": hint}
                else:
                    yield {"type": "error", "message": f"LLM 调用失败: {err_msg}"}
                return

            # ReAct fallback: parse <tool_call> blocks from text
            if not round_tool_calls and react_prompt:
                round_tool_calls = self._parse_react_tool_calls(round_text)
                if round_tool_calls:
                    logger.info(f"[REACT PARSE] sid={_sid} round={round_num} 从文本解析到 {len(round_tool_calls)} 个工具调用")

            if not round_tool_calls:
                logger.info(f"[LLM FINAL] sid={_sid} round={round_num} 无工具调用，输出最终回答 len={len(round_text)}")
                break

            # Keep only text BEFORE the first <tool_call> — discard any fabricated results after it
            _tc_pos = round_text.find("<tool_call>")
            clean_text = (round_text[:_tc_pos].strip() if _tc_pos > 0
                          else REACT_TOOL_BLOCK_RE.sub("", round_text).strip())
            # Strip thinking blocks from context — shown to user via SSE but not LLM history
            context_text = _strip_thinking(clean_text)
            messages.append({"role": "assistant", "content": context_text or None})
            yield {"type": "tool_calls", "tool_calls": round_tool_calls, "clean_text": clean_text}

            for tc in round_tool_calls:
                tc_id = tc.get("id", f"tc_{uuid.uuid4().hex[:8]}")
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                arguments_str = func.get("arguments", "{}")
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {"raw": arguments_str}

                _args_preview = str(arguments)[:120].replace("\n", " ")
                logger.info(
                    f"[TOOL START] sid={_sid} round={round_num} "
                    f"tool={tool_name} id={tc_id} args={_args_preview}"
                )
                yield {"type": "tool_start", "tool_call_id": tc_id,
                       "name": tool_name, "arguments": arguments}

                # ── Human-in-the-loop：所有工具执行前等待用户确认 ──
                if tool_name not in CONFIRM_SKIP_TOOLS:
                    _preview_str = _build_preview(tool_name, arguments)
                    logger.info(f"[CONFIRM WAIT] sid={_sid} tool={tool_name} id={tc_id} 等待用户确认(timeout=120s)")
                    yield {
                        "type": "tool_confirm_request",
                        "tool_call_id": tc_id,
                        "name": tool_name,
                        "preview": _preview_str,
                    }
                    # ── 持久化到 approval_requests（修复 Bug 1）──────────────
                    _appr_id = f"appr_{uuid.uuid4().hex[:12]}"
                    _appr_now = datetime.now(timezone.utc).isoformat()
                    _expires = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
                    try:
                        _appr_db = await get_db()
                        await _appr_db.execute(
                            """INSERT INTO approval_requests
                               (id, session_id, session_type, tool_call_id, tool_name,
                                arguments, preview, risk_level, status, expires_at, created_at)
                               VALUES (?, ?, 'chat', ?, ?,  ?, ?, 'medium', 'pending', ?, ?)""",
                            (
                                _appr_id, session_id, tc_id, tool_name,
                                json.dumps(arguments, ensure_ascii=False),
                                _preview_str, _expires, _appr_now,
                            ),
                        )
                        await _appr_db.commit()
                    except Exception as _ae:
                        logger.warning(f"[CONFIRM DB] 审批记录写入失败（不影响流程）: {_ae}")
                    # ─────────────────────────────────────────────────────────
                    _evt = asyncio.Event()
                    _pending_confirms[tc_id] = _evt
                    _confirm_t0 = time.time()
                    try:
                        await asyncio.wait_for(_evt.wait(), timeout=120)
                    except asyncio.TimeoutError:
                        _confirm_actions[tc_id] = "skip"
                        logger.warning(f"[CONFIRM TIMEOUT] sid={_sid} tool={tool_name} id={tc_id} 自动 skip")
                        try:
                            await _appr_db.execute(
                                "UPDATE approval_requests SET status='timeout' WHERE tool_call_id=?",
                                (tc_id,),
                            )
                            await _appr_db.commit()
                        except Exception:
                            pass
                    finally:
                        _pending_confirms.pop(tc_id, None)

                    _action = _confirm_actions.pop(tc_id, "allow")
                    _confirm_ms = int((time.time() - _confirm_t0) * 1000)
                    logger.info(f"[CONFIRM DONE] sid={_sid} tool={tool_name} id={tc_id} action={_action} wait={_confirm_ms}ms")
                    # 更新 DB 最终状态
                    try:
                        await _appr_db.execute(
                            "UPDATE approval_requests SET status=?, decided_at=? WHERE tool_call_id=?",
                            (_action, datetime.now(timezone.utc).isoformat(), tc_id),
                        )
                        await _appr_db.commit()
                    except Exception:
                        pass
                    if _action == "cancel":
                        logger.info(f"[AGENT CANCEL] sid={_sid} 用户取消任务")
                        yield {"type": "error", "message": "用户取消了任务"}
                        return
                    if _action == "skip":
                        logger.info(f"[TOOL SKIP] sid={_sid} tool={tool_name} id={tc_id}")
                        yield {"type": "tool_result", "tool_call_id": tc_id,
                               "name": tool_name, "result": {"skipped": True, "reason": "用户跳过"}}
                        messages.append({
                            "role": "user",
                            "content": f"[工具 {tool_name} 已被用户跳过]",
                        })
                        continue

                t0 = time.time()
                # 检查单次 run 内工具调用次数上限
                tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1
                _limit = MAX_TOOL_CALLS_PER_TOOL.get(tool_name, 0)
                if _limit and tool_call_counts[tool_name] > _limit:
                    result = {"error": f"工具 {tool_name} 在本次对话中已调用 {_limit} 次，已达上限，请直接给出最终答案。"}
                    success = 0
                    logger.warning(f"[TOOL LIMIT] sid={_sid} tool={tool_name} 调用次数超限({_limit})，返回错误")
                else:
                    try:
                        result = await self.tools.execute(tool_name, arguments)
                        success = 1
                    except Exception as e:
                        result = {"error": str(e)}
                        success = 0
                        logger.error(f"[TOOL ERROR] sid={_sid} tool={tool_name} id={tc_id}: {e}")
                duration_ms = int((time.time() - t0) * 1000)
                _has_files = bool(result.get("file_urls"))
                _exit_code = result.get("code", "n/a")
                _stderr_preview = str(result.get("stderr", "")).strip()[:120].replace("\n", "↵")
                logger.info(
                    f"[TOOL DONE] sid={_sid} tool={tool_name} id={tc_id} "
                    f"ok={success} duration={duration_ms}ms code={_exit_code} files={_has_files} "
                    f"out_len={len(str(result.get('stdout','')))} "
                    f"err={str(result.get('error',''))[:80] or 'none'} "
                    f"stderr={_stderr_preview or 'none'}"
                )
                await self._record_tool_usage(tool_name, duration_ms, success)
                await self._record_tool_call(
                    session_id=session_id,
                    tc_id=tc_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    duration_ms=duration_ms,
                    success=success,
                    round_num=len(all_tool_calls),
                )

                all_tool_calls.append({"tool_call_id": tc_id, "name": tool_name,
                                       "arguments": arguments, "result": result})
                yield {"type": "tool_result", "tool_call_id": tc_id,
                       "name": tool_name, "result": result}

                messages.append({
                    "role": "user",
                    "content": _compact_tool_result(tool_name, result),
                })

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[AGENT DONE] sid={_sid} elapsed={elapsed_ms}ms "
            f"in_tokens={total_input_tokens} out_tokens={total_output_tokens} "
            f"tool_calls={len(all_tool_calls)} "
            f"tools_used={list(dict.fromkeys(t['name'] for t in all_tool_calls))} "
            f"model={model}"
        )
        yield {
            "type": "done",
            "metadata": {
                "model": model,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "latency_ms": elapsed_ms,
                "tool_rounds": len(all_tool_calls),
                "skill": skill["name"] if skill else None,
            },
        }

    # ── Direct tool execution (no LLM) ──────────────────────────────────────

    async def _run_direct_tool(
        self, cmd: str, args_str: str, start_time: float
    ) -> AsyncIterator[dict]:
        tool_name = DIRECT_TOOL_COMMANDS[cmd]
        tc_id = f"tc_{uuid.uuid4().hex[:8]}"
        arguments = self._build_tool_arguments(tool_name, args_str)

        yield {"type": "tool_start", "tool_call_id": tc_id,
               "name": tool_name, "arguments": arguments}
        t0 = time.time()
        try:
            result = await self.tools.execute(tool_name, arguments)
            success = 1
        except Exception as e:
            result = {"error": str(e)}
            success = 0
        duration_ms = int((time.time() - t0) * 1000)
        await self._record_tool_usage(tool_name, duration_ms, success)

        yield {"type": "tool_result", "tool_call_id": tc_id,
               "name": tool_name, "result": result}

        formatted = self._format_tool_result(tool_name, result)
        yield {"type": "delta", "content": formatted}

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield {"type": "done", "metadata": {
            "model": "", "latency_ms": elapsed_ms,
            "input_tokens": 0, "output_tokens": 0,
            "tool_rounds": 1, "skill": None,
        }}

    def _build_tool_arguments(self, tool_name: str, args_str: str) -> dict:
        if tool_name == "bash":
            return {"command": args_str}
        if tool_name == "python_exec":
            return {"code": args_str}
        if tool_name == "web_search":
            return {"query": args_str}
        if tool_name == "http_request":
            return {"url": args_str.split()[0], "method": "GET"}
        if tool_name == "read_file":
            return {"path": args_str.strip()}
        return {"input": args_str}

    def _format_tool_result(self, tool_name: str, result: dict) -> str:
        if "error" in result:
            return f"\n\n❌ **{tool_name} 错误**: {result['error']}\n"
        if tool_name == "draw_diagram":
            return f"\n\n{result.get('output', '')}\n"
        if tool_name == "bash":
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            code = result.get("code", 0)
            out = []
            if stdout:
                out.append(f"```\n{stdout}\n```")
            if stderr:
                out.append(f"**stderr:**\n```\n{stderr}\n```")
            if not stdout and not stderr:
                out.append(f"✅ 命令执行完成（退出码 {code}）")
            return "\n\n" + "\n".join(out) + "\n"
        if tool_name == "python_exec":
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            out = []
            if stdout:
                out.append(f"```\n{stdout}\n```")
            if stderr:
                out.append(f"**stderr:**\n```\n{stderr}\n```")
            return "\n\n" + "\n".join(out) + "\n" if out else "\n\n✅ 执行完成\n"
        if tool_name == "web_search":
            results = result.get("results", [])
            if not results:
                return "\n\n🔍 未找到结果\n"
            lines = [f"**🔍 搜索: {result.get('query', '')}**\n"]
            for i, r in enumerate(results[:5], 1):
                if r.get("title"):
                    lines.append(f"{i}. **{r['title']}**")
                    if r.get("snippet"):
                        lines.append(f"   {r['snippet']}")
                elif r.get("text"):
                    lines.append(f"{i}. {r['text'][:200]}")
                if r.get("url"):
                    lines.append(f"   <{r['url']}>")
            return "\n\n" + "\n".join(lines) + "\n"
        if tool_name == "http_request":
            status = result.get("status_code", "")
            body = result.get("body", "")[:2000]
            return f"\n\n**HTTP {status}**\n```\n{body}\n```\n"
        return f"\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```\n"

    # ── ReAct text-based tool parsing ────────────────────────────────────────

    def _build_react_prompt(self, tool_schemas: list[dict]) -> str:
        if not tool_schemas:
            return ""
        return REACT_CALL_INSTRUCTION

    async def _record_tool_usage(self, tool_name: str, duration_ms: int, success: int) -> None:
        try:
            db = await get_db()
            await db.execute(
                "INSERT INTO tool_usages (tool_name, duration_ms, success) VALUES (?, ?, ?)",
                (tool_name, duration_ms, success),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to record tool usage for {tool_name}: {e}")

    async def _record_tool_call(
        self,
        session_id: str,
        tc_id: str,
        tool_name: str,
        arguments: dict,
        result: dict,
        duration_ms: int,
        success: int,
        round_num: int = 0,
    ) -> None:
        """写入 tool_call_logs — 完整 I/O 记录（修复 Bug 4）。"""
        try:
            db = await get_db()
            result_str = json.dumps(result, ensure_ascii=False)
            result_preview = str(
                result.get("stdout") or result.get("output") or result.get("error") or ""
            )[:512]
            result_size = len(result_str.encode("utf-8"))
            result_truncated = 0
            if result_size > 524_288:  # 512 KB
                result_str = result_str[:524_288] + "…[truncated]"
                result_truncated = 1
            status_str = "success" if success else "error"
            error_str = str(result.get("error", "")) if not success else None
            await db.execute(
                """INSERT INTO tool_call_logs
                   (session_id, session_type, tool_call_id, tool_name,
                    arguments, result, result_preview, result_size, result_truncated,
                    status, error, duration_ms, round_num)
                   VALUES (?, 'chat', ?, ?,  ?, ?, ?, ?, ?,  ?, ?, ?, ?)""",
                (
                    session_id, tc_id, tool_name,
                    json.dumps(arguments, ensure_ascii=False),
                    result_str, result_preview, result_size, result_truncated,
                    status_str, error_str, duration_ms, round_num,
                ),
            )
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to record tool call log for {tool_name}: {e}")

    def _parse_react_tool_calls(self, text: str) -> list[dict]:
        matches = REACT_TOOL_BLOCK_RE.findall(text)
        result = []
        for m in matches:
            try:
                parsed = json.loads(m)
                name = parsed.get("name", "")
                arguments = parsed.get("arguments", {})
                result.append({
                    "id": f"tc_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                })
            except json.JSONDecodeError as _jde:
                logger.warning(
                    f"[REACT PARSE FAIL] JSON解析失败，工具调用被丢弃: {_jde} "
                    f"raw={m[:200].replace(chr(10), '↵')}"
                )

        # Fallback: detect bare JSON blocks with {"name": ..., "arguments": ...}
        if not result:
            bare_re = re.compile(
                r'```(?:json)?\s*(\{"name"\s*:.*?"arguments"\s*:.*?\})\s*```',
                re.DOTALL,
            )
            for m in bare_re.findall(text):
                try:
                    parsed = json.loads(m)
                    name = parsed.get("name", "")
                    arguments = parsed.get("arguments", {})
                    if name:
                        result.append({
                            "id": f"tc_{uuid.uuid4().hex[:8]}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments, ensure_ascii=False),
                            },
                        })
                except json.JSONDecodeError:
                    pass
        return result

    # ── Skill slash command ───────────────────────────────────────────────────

    async def _check_skill_command(self, content: str) -> tuple[dict | None, str]:
        parts = content.split(None, 1)
        command = parts[0][1:]
        args = parts[1] if len(parts) > 1 else ""

        db = await get_db()
        row = await db.execute(
            "SELECT * FROM skills WHERE LOWER(name) = LOWER(?)", (command,)
        )
        skill = await row.fetchone()
        if skill:
            skill_dict = dict(skill)
            for k in ("allowed_tools", "arguments", "variables", "required_tools", "tags"):
                if k in skill_dict and isinstance(skill_dict[k], str):
                    try:
                        skill_dict[k] = json.loads(skill_dict[k])
                    except Exception:
                        pass
            if args and skill_dict.get("content"):
                skill_dict["content"] = skill_dict["content"].replace("$ARGUMENTS", args)
            actual_content = args if args else f"请使用 {skill_dict['name']} 技能"
            return skill_dict, actual_content
        return None, content

    # ── History ───────────────────────────────────────────────────────────────

    async def _load_history(self, session_id: str) -> list[dict[str, Any]]:
        db = await get_db()
        rows = await db.execute(
            """SELECT role, content, tool_calls, tool_call_id, name
               FROM chat_messages WHERE session_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (session_id, MAX_HISTORY_MESSAGES),
        )
        items = await rows.fetchall()
        messages = []
        for r in reversed(items):
            msg: dict[str, Any] = {"role": r["role"], "content": r["content"] or ""}
            if r["role"] == "assistant" and r["tool_calls"]:
                tc = r["tool_calls"]
                if isinstance(tc, str):
                    try:
                        tc = json.loads(tc)
                    except Exception:
                        tc = None
                if tc:
                    msg["tool_calls"] = tc
            if r["role"] == "tool":
                if r["tool_call_id"]:
                    msg["tool_call_id"] = r["tool_call_id"]
                if r["name"]:
                    msg["name"] = r["name"]
            messages.append(msg)
        return messages

    # ── Tool schemas ──────────────────────────────────────────────────────────

    def _get_tool_schemas(self, skill: dict | None = None,
                          allowed_tools: list[str] | None = None) -> list[dict]:
        # Priority: explicit allowed_tools > skill.allowed_tools > all tools
        whitelist = allowed_tools
        if whitelist is None and skill and skill.get("allowed_tools"):
            whitelist = skill["allowed_tools"]
        if whitelist is not None:
            schemas = []
            for name in whitelist:
                tool = self.tools.get(name)
                if tool:
                    schemas.append(tool.schema)
            return schemas
        all_tools = self.tools.list_all()
        schemas = []
        for t in all_tools:
            if t.get("is_enabled", True):
                tool_obj = self.tools.get(t["name"])
                if tool_obj:
                    schemas.append(tool_obj.schema)
        return schemas
