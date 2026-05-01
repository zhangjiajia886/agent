"""
Agent Runner —— LLM ReAct 循环驱动的漫剧 Agent。
用户选的模型 = 大脑，DB 中的工具 = 手。
"""
import json
import asyncio
from typing import AsyncIterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.agent_config import ModelConfig, ToolRegistry
from app.models.agent_prompt import AgentPrompt
from .openai_client import OpenAICompatClient, LLMResponse, LLMStreamChunk
from .agent_state import AgentStateStore
from .budget import BudgetController, BudgetAction
from .tool_executor import execute_tool
from .tool_result import normalize_tool_result
from .task_store import AgentTaskStore
from .task_planner import TaskPlanner
from .task_runtime import (
    apply_tool_result,
    audit_task,
    create_runtime_task,
    final_report_event,
    find_step_for_tool,
    step_update_event,
    task_created_event,
    task_update_event,
)

MAX_ITERATIONS = 15
LLM_TIMEOUT = 120
TOKEN_COMPACT_THRESHOLD = 8000
TOKEN_BUDGET = 32000
_CHARS_PER_TOKEN = 2.5

MAX_TOOL_CALLS_PER_TOOL: dict[str, int] = {
    # 漫剧工具
    "generate_image": 8,
    "generate_image_with_face": 6,
    "edit_image": 4,
    "image_to_video": 3,
    "upscale_image": 4,
    "text_to_speech": 6,
    "merge_media": 2,
    "add_subtitle": 2,
    # 通用工具
    "read_file": 6,
    "write_file": 5,
    "edit_file": 4,
    "bash": 8,
    "python_exec": 5,
    "web_search": 4,
    "web_fetch": 4,
    "grep_search": 4,
    "find_files": 4,
    "list_dir": 4,
    "http_request": 4,
}

# ── 工具安全分类（三级审批）──
# L0: 始终自动执行（只读、无副作用）
AUTO_APPROVE_TOOLS: set[str] = {
    "read_file", "list_dir", "find_files", "grep_search",
    "web_search", "web_fetch",
}
# L1: auto_mode 开启时自动执行（创作类，无破坏性）
CREATIVE_AUTO_APPROVE_TOOLS: set[str] = {
    "generate_image", "generate_image_with_face", "edit_image",
    "image_to_video", "upscale_image", "text_to_speech",
    "merge_media", "add_subtitle",
    "write_file", "python_exec",
}
_SAFE_WRITE_DIRS = {"agent_outputs", "uploads"}


def needs_approval(tool_name: str, args: dict, auto_mode: bool = False) -> bool:
    """判断工具是否需要用户审批"""
    if tool_name in AUTO_APPROVE_TOOLS:
        return False
    if auto_mode and tool_name in CREATIVE_AUTO_APPROVE_TOOLS:
        if tool_name == "write_file":
            path = args.get("path", "")
            return not any(safe in path for safe in _SAFE_WRITE_DIRS)
        if tool_name == "bash":
            cmd = args.get("command", "").strip()
            ro = ("ls ", "pwd", "cat ", "head ", "tail ", "file ", "wc ", "find ", "grep ", "echo ")
            return not any(cmd.startswith(p) for p in ro)
        return False
    return True
# L2: 其余所有工具始终需要用户确认

REACT_CALL_INSTRUCTION = """
## 工具调用格式
如需使用工具，在回复中插入：
<tool_call>{"name": "工具名", "arguments": {...}}</tool_call>
⚠️ 生成 </tool_call> 后立即停止，不要预测工具结果。
"""


# ═══════════════════ System Prompt ═══════════════════

DEFAULT_SYSTEM_PROMPT = """你是「漫剧 Agent」，一个专业的 AI 漫画和视觉创作助手。

## 意图判定（最高优先级）
- **纯聊天/问答**: 用户在打招呼、问你是谁、闲聊、问问题 → 直接文字回复，**禁止调用任何工具**，不要主动探索环境
- **需要工具的任务**: 用户要求搜索/生成/编辑/读写/执行 → 立即调工具
- **模糊意图**: 不确定用户要做什么 → 先询问意图，不要猜测

## 你的能力
你可以通过工具完成以下任务：
- 根据用户描述生成各种风格的图片（仙侠/水墨/盲盒Q版/动漫/写实/Flux 等）
- 将图片动态化为视频
- 对已有图片进行编辑修改
- 超分放大提升图片质量
- 语音合成
- 读写文件、执行代码、搜索网页等通用操作

## 执行策略（仅当判定为“需要工具的任务”时）
收到任务后按以下循环执行：
1. **理解需求**: 先判断用户到底要完成什么。
2. **任务拆分**: 把任务拆成可执行步骤。
3. **执行工具**: 对当前最该执行的步骤调用对应工具。
4. **结果思考**: 每个工具返回后，分析结果是否满足当前步骤。
5. **重新规划**: 基于已产出的结果，判断下一步还需要调用什么工具。
6. **空工具审计**: 如果你没有返回工具调用，系统会要求你审计所有已完成内容；若任务彻底完成则总结结束，若未完成则列出剩余 TODO 并继续下一步。

示例：用户说“搜索X，写入文件，生成图片”
- 第1轮: 理解需求并调用 web_search
- 第2轮: 分析搜索结果，调用 write_file
- 第3轮: 分析文件写入结果，调用 generate_image
- 第4轮: 分析图片结果，无需继续工具时纯文字汇报并结束

## 工具选择优先级
有专用工具时必须优先使用，禁止用 bash 替代：
- 读文件 → read_file（禁止 bash cat）
- 写文件 → write_file（禁止 bash echo >）
- 搜索文件内容 → grep_search（禁止 bash grep）
- 查找文件 → find_files（禁止 bash find）
- HTTP 请求 → http_request（禁止 bash curl）
bash 仅用于: 系统命令、管道操作、或确实没有专用工具的场景

## 图像提示词规范
- 必须使用英文
- 开头加质量词: masterpiece, best quality, highly detailed
- 根据 style 参数添加风格词:
  - xianxia: xianxia style, ancient chinese, elegant hanfu, ethereal
  - anime: anime style, beautiful, sparkling eyes, vibrant colors
  - ink: ink wash painting, sumi-e, monochrome
  - blindbox: chibi, 3d render, cute, pastel colors, kawaii
  - realistic: photorealistic, cinematic, 8k uhd
  - flux: ultra high quality, professional photography
- style 参数可选值: xianxia / anime / ink / blindbox / realistic / flux

## 执行规范
1. 严格按用户要求的数量执行。用户说“生成1张图”就只生成1张，不要自作主张多做。
2. 每次工具执行后，立即检查结果:
   - 成功: 记录产出（文件路径/URL），继续下一步
   - 失败: 分析原因，尝试修复（最多重试1次），仍失败则汇报并建议替代方案
3. **结束规则**: 所有步骤完成后，不再调用工具，输出最终汇报即可。
4. 保持工作记忆: 记住每步产出的文件路径，后续步骤直接引用
5. 完成后简短询问用户是否满意，不要自动生成变体

## 异常处理
- **用户拒绝工具**: 停止该操作，询问用户是否需要调整方案。绝不重复调用被拒绝的工具。
- **工具连续失败**: 最多重试1次。2次失败后汇报错误并建议替代方案，不要无限重试。
- **文件路径**: 工作记忆中的路径就是正确路径，直接使用，不要用 find_files 重新搜索。

## 重要
- 每次只做用户要求的事，不要多余操作
- 回复要简洁，不要长篇大论重复结果"""


# ═══════════════════ Token 管理函数 ═══════════════════

def _estimate_tokens(messages: list[dict]) -> int:
    """估算消息列表的 token 数"""
    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    return int(total_chars / _CHARS_PER_TOKEN)


def _compact_history(messages: list[dict]) -> list[dict]:
    """压实历史：保留 system + 最近 6 条完整消息，中间的工具结果截断（媒体路径永不丢失）"""
    if len(messages) <= 8:
        return messages
    result = [messages[0]]  # system prompt
    middle = messages[1:-6]
    recent = messages[-6:]
    for m in middle:
        if m.get("role") == "tool":
            content = m.get("content", "")
            if len(content) > 200:
                truncated = content[:200] + "...(已截断)"
                media_paths = re.findall(
                    r'(?:图片|视频|音频)(?:URL|路径): (\S+)', content
                )
                if media_paths:
                    truncated += "\n关键产出: " + ", ".join(media_paths)
                result.append({**m, "content": truncated})
            else:
                result.append(m)
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            result.append({"role": "assistant", "content": m.get("content", "")[:100] + "...", "tool_calls": m["tool_calls"]})
        else:
            result.append(m)
    result.extend(recent)
    return result


def _compact_tool_result(tool_name: str, result: dict) -> str:
    """工具结果压缩：只保留关键信息，约 90% token 节省"""
    if result.get("error") or result.get("status") == "error":
        return f"[{tool_name}] ❌ 错误: {str(result.get('error', '未知错误'))[:300]}"
    if result.get("status") == "not_implemented":
        return f"[{tool_name}] ⚠️ 功能尚未实现"

    parts = [f"[{tool_name}] ✓"]
    # 媒体类（同时输出 URL 和文件路径，方便后续工具引用）
    if result.get("image_url"):
        parts.append(f"图片URL: {result['image_url']}")
    if result.get("image_path"):
        parts.append(f"图片路径: {result['image_path']}")
    if result.get("video_url"):
        parts.append(f"视频URL: {result['video_url']}")
    if result.get("video_path"):
        parts.append(f"视频路径: {result['video_path']}")
    if result.get("audio_url"):
        parts.append(f"音频URL: {result['audio_url']}")
    if result.get("audio_path"):
        parts.append(f"音频路径: {result['audio_path']}")
    # 通用工具结果
    if "stdout" in result:
        out = result["stdout"].strip()
        parts.append(f"stdout: {out[:500]}" if out else "(无输出)")
        if result.get("stderr", "").strip():
            parts.append(f"stderr: {result['stderr'][:200]}")
        parts.append(f"exit={result.get('code', '?')}")
    if "content" in result and tool_name in ("read_file", "web_fetch"):
        parts.append(f"内容({len(result['content'])}字): {result['content'][:300]}")
    if "results" in result and tool_name == "web_search":
        items = result["results"]
        parts.append(f"找到 {len(items)} 条结果")
        for r in items[:3]:
            parts.append(f"  - {r.get('title', '')}: {r.get('snippet', '')[:80]}")
    if result.get("success") and tool_name == "write_file":
        parts.append(f"已写入 {result.get('path')} ({result.get('bytes_written', 0)} bytes)")
    if result.get("ok") and tool_name == "edit_file":
        parts.append(f"已编辑 {result.get('path')}")
    if "matches" in result and tool_name == "grep_search":
        parts.append(f"搜索结果: {str(result['matches'])[:400]}")
    if "matches" in result and tool_name == "find_files":
        parts.append(f"找到 {result.get('count', 0)} 个文件")
    if "items" in result and tool_name == "list_dir":
        items = result["items"]
        parts.append(f"{len(items)} 项")
        for it in items[:10]:
            parts.append(f"  {'📁' if it.get('type')=='directory' else '📄'} {it['name']}")
    return " | ".join(parts)


def _tool_action_description(tool_name: str, args: dict) -> str:
    """根据工具名和参数生成人类可读的操作描述（用于 thinking 事件）"""
    desc_map = {
        "generate_image": lambda a: f"生成图像，主题摘要：{a.get('prompt', '')[:60]}...；风格：{a.get('style', '默认')}",
        "generate_image_with_face": lambda a: f"执行人像一致性生成，主题摘要：{a.get('prompt', '')[:60]}...",
        "edit_image": lambda a: f"执行图像编辑，修改要求：{a.get('instruction', '')[:60]}...",
        "image_to_video": lambda a: f"执行图像动态化，运动描述：{a.get('motion_prompt', '默认运动')[:50]}",
        "text_to_speech": lambda a: f"执行语音合成，文本摘要：{a.get('text', '')[:40]}...",
        "upscale_image": lambda a: f"执行图像超分，源文件：{a.get('source_image', '')}",
        "bash": lambda a: f"执行系统命令：`{a.get('command', '')[:80]}`",
        "read_file": lambda a: f"读取文件：{a.get('path', '')}",
        "write_file": lambda a: f"写入文件：{a.get('path', '')}（{len(a.get('content', ''))} 字符）",
        "edit_file": lambda a: f"编辑文件：{a.get('path', '')}",
        "python_exec": lambda a: f"执行 Python 代码：{(a.get('code') or '')[:60]}...",
        "web_search": lambda a: f"检索网络信息：{a.get('query', '')}",
        "web_fetch": lambda a: f"抓取网页内容：{a.get('url', '')[:60]}",
        "grep_search": lambda a: f"检索文件内容：{a.get('query', '')}（范围：{a.get('path', '.')}）",
        "find_files": lambda a: f"检索文件路径：{a.get('pattern', '')}（范围：{a.get('base_dir', '.')}）",
        "list_dir": lambda a: f"查看目录：{a.get('path', '.')}",
        "http_request": lambda a: f"发起 HTTP 请求：{a.get('method', 'GET')} {a.get('url', '')[:60]}",
    }
    fn = desc_map.get(tool_name)
    if fn:
        try:
            return fn(args)
        except Exception:
            pass
    return f"🔧 {tool_name}: {json.dumps(args, ensure_ascii=False)[:80]}"


import re

def _parse_react_tool_calls(text: str) -> list:
    """解析文本中的 <tool_call>...</tool_call> 块（ReAct 降级）"""
    from .openai_client import ToolCall
    pattern = r"<tool_call>\s*(\{[\s\S]*?\})\s*</tool_call>"
    matches = re.findall(pattern, text)
    calls = []
    for i, m in enumerate(matches):
        try:
            data = json.loads(m)
            calls.append(ToolCall(
                id=f"react_{i}",
                name=data.get("name", ""),
                arguments=data.get("arguments", {}),
            ))
        except json.JSONDecodeError:
            logger.warning(f"[AgentRunner] ReAct 解析失败: {m[:100]}")
    return calls


# ═══════════════════ 动态 LLM 客户端 ═══════════════════

def create_llm_client(model_config: ModelConfig) -> tuple[OpenAICompatClient, dict]:
    """根据 DB 模型配置创建 LLM 客户端，返回 (client, model_params)"""
    params = model_config.model_params or {}
    return OpenAICompatClient(
        base_url=model_config.base_url,
        api_key=model_config.api_key or "",
        model=model_config.model_id,
    ), params


# ═══════════════════ 工具定义构建 ═══════════════════

async def build_tool_definitions(db: AsyncSession) -> list[dict]:
    """从 DB tool_registry 读取已启用工具，转为 OpenAI tools 格式"""
    result = await db.execute(
        select(ToolRegistry)
        .where(ToolRegistry.is_enabled == True)
        .order_by(ToolRegistry.sort_order)
    )
    tools = []
    for tool in result.scalars():
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        })
    return tools


# ═══════════════════ System Prompt 加载 ═══════════════════

async def load_system_prompt(db: AsyncSession) -> str:
    """从 DB agent_prompt 表加载 system prompt，无则返回默认值"""
    result = await db.execute(
        select(AgentPrompt)
        .where(AgentPrompt.node_name == "system", AgentPrompt.is_enabled == True)
        .order_by(AgentPrompt.sort_order)
    )
    row = result.scalar_one_or_none()
    if row and row.content:
        return row.content
    return DEFAULT_SYSTEM_PROMPT


# ═══════════════════ 对话历史构建 ═══════════════════

def build_messages(
    system_prompt: str,
    history: list[dict],
    user_message: str,
) -> list[dict]:
    """构建 LLM 消息列表: system + 历史 + 当前消息"""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-20:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


# ═══════════════════ ReAct Agent 循环 ═══════════════════

def _should_yield_thinking(text: str) -> bool:
    """判断 thinking 内容是否值得展示给用户（过滤英文内部推理）"""
    stripped = text.strip()
    if not stripped:
        return False
    if re.search(r'[\u4e00-\u9fff]', stripped):
        return True
    if stripped[0] in '\U0001f527\U0001f50d\U0001f3a8\U0001f3ac\U0001f4dd\U0001f504\U0001f4bb\U0001f4c1\U0001f4c4\U0001f9e0\u2705\u274c\u26a0\ufe0f':
        return True
    return False


async def agent_stream(
    user_message: str,
    model_config: ModelConfig,
    db: AsyncSession,
    conversation_history: Optional[list[dict]] = None,
    approval_queue: Optional[asyncio.Queue] = None,
    auto_mode: bool = False,
    conversation_id: int | None = None,
    user_id: int | None = None,
) -> AsyncIterator[dict]:
    """
    LLM ReAct 循环：思考 → 行动 → 观察 → 再思考。
    yield 的事件与前端 AgentEvent 完全兼容。

    防护机制：
    - Token 预算管理：估算 + 压实 + 紧张提示
    - 工具结果压缩：~90% token 节省
    - 工具调用次数限制：防 LLM 死循环
    - 强制摘要轮：最后一轮移除工具强制回答
    - ReAct XML 降级：解析 <tool_call> 标签
    - 流式输出：逐 token delta 事件
    """
    llm, model_params = create_llm_client(model_config)
    llm.timeout = LLM_TIMEOUT
    temperature = model_params.get("temperature", 0.7)
    max_tokens = model_params.get("max_tokens", 4096)
    top_p = model_params.get("top_p", 1.0)
    frequency_penalty = model_params.get("frequency_penalty", 0.0)
    presence_penalty = model_params.get("presence_penalty", 0.0)

    tools = await build_tool_definitions(db)
    system_prompt = await load_system_prompt(db)
    history = conversation_history or []
    messages = build_messages(system_prompt, history, user_message)
    model_name = model_config.model_id
    planner = TaskPlanner()
    runtime_task = planner.plan_to_runtime(user_message)
    task_store = AgentTaskStore() if conversation_id else None
    state_store = AgentStateStore()
    lock_owner = f"conversation:{conversation_id or 0}:user:{user_id or 0}"
    lock_acquired = await state_store.acquire_task_lock(runtime_task.task_uid, lock_owner)
    if not lock_acquired:
        yield {"type": "error", "task_uid": runtime_task.task_uid, "content": "任务正在运行中，请稍后再试"}
        return

    async def persist_event(event: dict) -> dict:
        if task_store:
            await task_store.append_event(event)
        return event

    if task_store:
        await task_store.create_task(
            runtime_task,
            conversation_id=conversation_id,
            user_id=user_id,
            model_id=model_name,
            auto_mode=auto_mode,
        )
        await task_store.create_steps(runtime_task)

    budget_ctrl = BudgetController()
    force_tool_choice: Optional[str] = None  # "required" 强制调工具
    no_tool_streak = 0  # 连续无工具调用轮数
    no_tool_reviewed = False  # 空工具后是否已经要求模型审计任务完成度
    rejected_tools: dict[str, int] = {}  # 被拒绝的工具计数
    has_rejection_this_round = False  # 本轮是否有工具被拒绝
    artifacts: list[str] = []  # 工作记忆：收集每步产出的媒体 URL

    logger.info(
        f"[AgentRunner] start model={model_name} "
        f"tools={len(tools)} history={len(history)} "
        f"temperature={temperature} max_tokens={max_tokens}"
    )

    yield await persist_event(task_created_event(runtime_task))

    tool_names_str = ", ".join(t["function"]["name"] for t in tools) if tools else "无"
    yield {
        "type": "thinking",
        "content": f"模型：{model_name}\n已加载工具：{len(tools)} 个\n工具列表：{tool_names_str}\n历史消息：{len(history)} 条",
    }

    for iteration in range(MAX_ITERATIONS + 1):
        is_summary_round = iteration == MAX_ITERATIONS

        # ── 工作记忆注入 ──
        if artifacts and iteration > 0:
            mem = "[工作记忆] 当前已生成的资源:\n" + "\n".join(artifacts)
            if messages and messages[-1].get("role") == "system" and messages[-1].get("content", "").startswith("[工作记忆]"):
                messages[-1] = {"role": "system", "content": mem}
            else:
                messages.append({"role": "system", "content": mem})

        # ── Token 预算管理 ──
        est_tokens = _estimate_tokens(messages)
        if est_tokens > TOKEN_COMPACT_THRESHOLD and not is_summary_round:
            before = est_tokens
            messages = _compact_history(messages)
            after = _estimate_tokens(messages)
            logger.info(f"[AgentRunner] Token 压实: {before} -> {after}")
            est_tokens = after

        budget_pct = est_tokens / TOKEN_BUDGET
        if budget_pct >= 0.75 and not is_summary_round:
            logger.warning(f"[AgentRunner] Token 紧张: {est_tokens}/{TOKEN_BUDGET} ({budget_pct:.0%})")

        # ── 强制摘要轮 ──
        current_tools = tools
        if is_summary_round:
            messages.append({
                "role": "user",
                "content": "[系统提示] 已达到最大工具轮次，请根据已有结果给出完整的最终回答，不要再调用任何工具。",
            })
            current_tools = None
            yield {"type": "thinking", "content": "\U0001f4dd 达到最大轮次，生成最终摘要..."}

        # ── 流式 LLM 调用 ──
        accumulated_text = ""
        accumulated_thinking = ""
        final_tool_calls = None

        try:
            current_tool_choice = force_tool_choice if (current_tools and force_tool_choice) else None
            force_tool_choice = None  # 用完即清
            if current_tool_choice:
                logger.info(f"[AgentRunner] 使用 tool_choice={current_tool_choice}")
            async for chunk in llm.chat_stream_with_tools(
                messages=messages,
                tools=current_tools if current_tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                tool_choice=current_tool_choice,
            ):
                if chunk.thinking:
                    accumulated_thinking += chunk.thinking
                    if _should_yield_thinking(chunk.thinking):
                        yield {"type": "thinking", "content": chunk.thinking}
                elif chunk.text:
                    accumulated_text += chunk.text
                    yield {"type": "delta", "content": chunk.text}
                elif chunk.is_done:
                    final_tool_calls = chunk.tool_calls
                    budget_ctrl.record_tokens(chunk.input_tokens, chunk.output_tokens)
        except Exception as e:
            logger.error(f"[AgentRunner] LLM call failed iter={iteration}: {e}")
            runtime_task.status = "failed"
            if task_store:
                await task_store.update_task(runtime_task, error={"message": str(e), "stage": "llm_call"})
            yield await persist_event({"type": "error", "task_uid": runtime_task.task_uid, "content": f"LLM 调用失败: {e}"})
            await state_store.release_task_lock(runtime_task.task_uid)
            return

        # ── ReAct XML 降级解析 ──
        if not final_tool_calls and accumulated_text and not is_summary_round:
            parsed = _parse_react_tool_calls(accumulated_text)
            if parsed:
                final_tool_calls = parsed
                clean_text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", accumulated_text).strip()
                accumulated_text = clean_text if clean_text else ""
                logger.info(f"[AgentRunner] ReAct 解析到 {len(parsed)} 个工具调用")

        logger.info(
            f"[AgentRunner] iter={iteration} tool_calls={len(final_tool_calls or [])} "
            f"text_len={len(accumulated_text)} force_was={current_tool_choice}"
        )

        # ── 文字回复（delta 已流式发送，此处只更新消息历史） ──
        if accumulated_text:
            messages.append({"role": "assistant", "content": accumulated_text})

        # ── 无工具调用 → 显式完成检测 + 自动续行 ──
        if not final_tool_calls:
            no_tool_streak += 1
            text = accumulated_text.strip()

            # 1. 检测显式完成信号（扩展中文信号）
            task_done = bool(
                "[TASK_DONE]" in text
                or re.search(r"(任务已完成|已全部完成|以上是.*结果|执行完毕.*汇报)", text)
            )
            # 2. 检测收尾性文字（不应被当作计划）
            is_wrap_up = bool(text and re.search(
                r"(如果你需要|如果你要|如果你愿意|你也可以|我还可以|我也可以|需要我继续|是否满意|是否需要)", text
            ))
            # 3. 检测是否有未执行的计划（排除收尾建议）
            has_plan = bool(not is_wrap_up and text and (
                re.search(r"(?:第[1-9一二三四五六]步|步骤\s*[1-9]|^\s*\d+[\.\)、\)])", text, re.M)
                or re.search(r"(分\s*\d+\s*步|开始执行|先.*然后|我先执行|先生成|再做|基于.*做)", text)
            ))
            tools_executed = budget_ctrl.usage.tool_calls > 0
            incomplete = bool(text and re.search(
                r"(剩余\s*TODO|尚未完成|未完成|还需要|需要继续|下一步|先执行第?\s*[1-9一二三四五六]?\s*步)",
                text,
            ))
            if incomplete and no_tool_reviewed:
                audit = audit_task(runtime_task, text)
                runtime_task.status = "incomplete"
                incomplete_event = {
                    "type": "incomplete",
                    "task_uid": runtime_task.task_uid,
                    "status": "incomplete",
                    "remaining_steps": audit["remaining_steps"],
                    "content": "模型审计后判断仍有任务未完成，但本轮没有返回工具调用。请继续发送或调整提示以推进剩余 TODO。",
                }
                if task_store:
                    await task_store.update_task(runtime_task)
                yield await persist_event(incomplete_event)
                break
            messages.append({
                "role": "user",
                "content": (
                    "[系统审计] 你本轮没有返回工具调用。请基于用户原始需求、已执行工具结果和当前产物进行判断：\n"
                    "1. 如果所有任务已经彻底完成，请不要调用工具，直接输出最终总结报告。\n"
                    "2. 如果仍有任务没完成，请先列出剩余 TODO，然后自主决定下一步是否需要调用工具。\n"
                    "3. 不要为了调用而调用工具；只有确实需要执行下一步时才调用工具。"
                ),
            })
            no_tool_reviewed = True
            yield {"type": "thinking", "content": "未检测到新的工具调用，正在审计任务是否已彻底完成。"}
            continue

        # ── 有工具调用，重置空轮计数和拒绝标记 ──
        no_tool_streak = 0
        no_tool_reviewed = False
        has_rejection_this_round = False

        # ── 工具调用 → 逐个执行 ──
        assistant_msg: dict = {"role": "assistant", "content": accumulated_text or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for tc in final_tool_calls
        ]
        if accumulated_text:
            messages.pop()
        messages.append(assistant_msg)

        tool_names_list = [tc.name for tc in final_tool_calls]
        # 生成详细的工具执行计划
        action_lines = [f"\n执行计划：共 {len(final_tool_calls)} 项操作。"]
        for tc in final_tool_calls:
            action_lines.append(f"- {_tool_action_description(tc.name, tc.arguments)}")
        yield {
            "type": "thinking",
            "content": "\n".join(action_lines) + "\n",
        }

        for tc in final_tool_calls:
            # ── P11 工具预算检查 ──
            tool_decision = budget_ctrl.pre_tool_check(tc.name)
            if tool_decision.action == BudgetAction.BLOCK:
                result = {"error": tool_decision.message}
                yield {"type": "tool_start", "tool": tc.name, "input": tc.arguments, "description": _tool_action_description(tc.name, tc.arguments)}
                yield {
                    "type": "tool_done", "tool": tc.name,
                    "result": json.dumps(result, ensure_ascii=False),
                }
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": _compact_tool_result(tc.name, result),
                })
                continue
            if tool_decision.action == BudgetAction.WARN:
                logger.warning(f"[Budget] {tool_decision.message}")
            budget_ctrl.record_tool_call(tc.name)

            desc = _tool_action_description(tc.name, tc.arguments)
            _needs_approval = (
                needs_approval(tc.name, tc.arguments, auto_mode)
                and approval_queue is not None
            )

            if _needs_approval:
                # ── 需要用户确认 ──
                current_step = find_step_for_tool(runtime_task, tc.name)
                current_step.status = "awaiting_approval"
                current_step.inputs = tc.arguments
                runtime_task.status = "awaiting_approval"
                runtime_task.current_step_uid = current_step.step_uid
                if task_store:
                    await task_store.update_task(runtime_task)
                    await task_store.update_step(runtime_task.task_uid, current_step)
                await state_store.set_approval_waiting(runtime_task.task_uid, {
                    "task_uid": runtime_task.task_uid,
                    "step_uid": current_step.step_uid,
                    "tool": tc.name,
                    "tool_call_id": tc.id,
                    "input": tc.arguments,
                })
                yield await persist_event(task_update_event(runtime_task, f"等待确认：{current_step.title}"))
                yield await persist_event(step_update_event(runtime_task, current_step))
                yield await persist_event({
                    "type": "tool_confirm",
                    "task_uid": runtime_task.task_uid,
                    "step_uid": current_step.step_uid,
                    "tool": tc.name,
                    "input": tc.arguments,
                    "description": desc,
                    "tool_call_id": tc.id,
                })
                logger.info(f"[AgentRunner] 等待用户确认: {tc.name}")
                try:
                    approval = await asyncio.wait_for(approval_queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    approval = {"action": "reject", "reason": "确认超时(5分钟)"}
                await state_store.clear_approval(runtime_task.task_uid)

                if approval.get("action") != "approve":
                    reason = approval.get("reason", "用户拒绝")
                    result = {"error": f"用户拒绝执行: {reason}", "status": "rejected"}
                    standard_result = normalize_tool_result(tc.name, result, tc.id)
                    for runtime_event in apply_tool_result(runtime_task, current_step, standard_result):
                        if task_store:
                            if runtime_event.get("type") == "step_update":
                                await task_store.update_step(runtime_task.task_uid, current_step)
                            await task_store.update_task(runtime_task)
                        yield await persist_event(runtime_event)
                    rejected_tools[tc.name] = rejected_tools.get(tc.name, 0) + 1
                    has_rejection_this_round = True
                    yield await persist_event({
                        "type": "tool_done", "tool": tc.name,
                        "result": json.dumps(result, ensure_ascii=False),
                    })
                    reject_hint = f"用户拒绝了 {tc.name}。"
                    if rejected_tools[tc.name] >= 2:
                        reject_hint += "该工具已被连续拒绝，请停止使用此工具，询问用户是否需要其他方案。"
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": reject_hint,
                    })
                    continue

            current_step = find_step_for_tool(runtime_task, tc.name)
            await state_store.increment_budget_counter(runtime_task.task_uid, f"tool:{tc.name}")
            await state_store.increment_budget_counter(runtime_task.task_uid, "tool_calls")
            current_step.status = "running"
            current_step.inputs = tc.arguments
            runtime_task.status = "running"
            runtime_task.current_step_uid = current_step.step_uid
            if task_store:
                await task_store.update_task(runtime_task)
                await task_store.update_step(runtime_task.task_uid, current_step)
                await task_store.start_tool_invocation(runtime_task.task_uid, current_step.step_uid, tc.id, tc.name, tc.arguments)
            yield await persist_event(task_update_event(runtime_task, f"正在执行：{current_step.title}"))
            yield await persist_event(step_update_event(runtime_task, current_step))
            yield await persist_event({"type": "tool_start", "task_uid": runtime_task.task_uid, "step_uid": current_step.step_uid, "tool": tc.name, "input": tc.arguments, "description": desc})

            logger.info(f"[AgentRunner] exec tool={tc.name} args={tc.arguments}")
            try:
                result = await execute_tool(tc.name, tc.arguments)
            except Exception as e:
                logger.error(f"[AgentRunner] tool exec failed: {tc.name}: {e}")
                result = {"error": str(e), "status": "failed"}

            standard_result = normalize_tool_result(tc.name, result, tc.id)
            tool_done_event = {
                "type": "tool_done",
                "task_uid": runtime_task.task_uid,
                "step_uid": current_step.step_uid,
                "tool": tc.name,
                "result": json.dumps(result, ensure_ascii=False),
                "standard_result": standard_result.to_dict(),
                "image_url": result.get("image_url"),
                "video_url": result.get("video_url"),
                "audio_url": result.get("audio_url"),
            }
            if task_store:
                await task_store.finish_tool_invocation(tc.id, tc.name, result, standard_result)
            yield await persist_event(tool_done_event)
            for runtime_event in apply_tool_result(runtime_task, current_step, standard_result):
                if task_store:
                    if runtime_event.get("type") == "artifact_created":
                        await task_store.create_artifact(runtime_task.task_uid, current_step.step_uid, runtime_event.get("artifact") or {})
                    if runtime_event.get("type") == "step_update":
                        await task_store.update_step(runtime_task.task_uid, current_step)
                    await task_store.update_task(runtime_task)
                yield await persist_event(runtime_event)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": _compact_tool_result(tc.name, result),
            })

            # ── 收集产出到工作记忆 ──
            if result.get("image_url"):
                artifacts.append(f"图片: {result['image_url']}")
            if result.get("video_url"):
                artifacts.append(f"视频: {result['video_url']}")
            if result.get("audio_url"):
                artifacts.append(f"音频: {result['audio_url']}")
            if result.get("success") and result.get("path"):
                artifacts.append(f"文件: {result['path']}")

        if not is_summary_round:
            yield {
                "type": "thinking",
                "content": f"\U0001f504 工具执行完毕，继续下一步... (第 {iteration + 2}/{MAX_ITERATIONS} 轮)",
            }

    usage = budget_ctrl.usage
    metadata = {
        "model": model_name,
        "iterations": min(iteration + 1, MAX_ITERATIONS + 1),
        "total_tool_calls": usage.tool_calls,
        "tools_used": list(usage.calls_per_tool.keys()),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "budget_usage": usage.to_dict(),
    }
    audit = audit_task(runtime_task, accumulated_text if "accumulated_text" in locals() else "")
    final_event = final_report_event(runtime_task, audit, metadata)
    if task_store:
        await task_store.update_task(runtime_task, final_report=final_event.get("final_report"))
    yield await persist_event(final_event)
    await state_store.clear_budget_counter(runtime_task.task_uid)
    await state_store.release_task_lock(runtime_task.task_uid)
