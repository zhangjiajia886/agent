"""
OpenAI 兼容 LLM 客户端 —— 用于 AIPro 聚合平台（Claude / GPT / Gemini）
支持: chat / chat_with_tools / stream
"""
import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import httpx
from loguru import logger


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    thinking: Optional[str] = None


@dataclass
class LLMStreamChunk:
    """流式输出的单个片段"""
    text: str = ""
    is_done: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    tool_calls: Optional[list[ToolCall]] = None
    thinking: Optional[str] = None


_MODELS_NO_TOOLS_STREAM: set[str] = set()


class OpenAICompatClient:
    """OpenAI 兼容接口客户端，支持 tool_use（function calling）"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ─────────── 非流式 + 工具调用 ───────────

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> LLMResponse:
        """非流式调用，返回完整回复（可能含 tool_calls）"""
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(
            f"[OpenAI] request model={self.model} msgs={len(messages)} "
            f"tools={len(tools or [])} url={self.base_url}/chat/completions"
        )

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
            resp = await c.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code != 200:
                body = resp.text[:500]
                logger.error(f"[OpenAI] {resp.status_code} response: {body}")
                logger.error(f"[OpenAI] payload keys: {list(payload.keys())} model={self.model}")
                resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        result = LLMResponse(
            content=msg.get("content"),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
            thinking=msg.get("reasoning_content") or msg.get("thinking"),
        )

        # 解析 tool_calls
        raw_calls = msg.get("tool_calls", [])
        for tc in raw_calls:
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {"raw": args_str}
            result.tool_calls.append(ToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=args,
            ))

        logger.debug(
            f"[OpenAI] response finish={result.finish_reason} "
            f"content_len={len(result.content or '')} "
            f"tool_calls={len(result.tool_calls)}"
        )
        return result

    # ─────────── 流式 + 工具调用 ───────────

    async def chat_stream_with_tools(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        tool_choice: Optional[str] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        流式输出，支持 tool_calls 累积 + Thinking/Reasoning。
        逐 chunk yield LLMStreamChunk，最终 chunk 含 is_done=True + tool_calls。
        tool_choice: None/"auto"(默认) | "required"(强制调工具) | "none"(禁止调工具)
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": True,
        }
        # 如果模型已知不支持 stream+tools，跳过 tools
        skip_tools = self.model in _MODELS_NO_TOOLS_STREAM
        if tools and not skip_tools:
            payload["tools"] = tools
            effective_choice = tool_choice or "auto"
            # Claude 通过 OpenAI 兼容代理时，"required" 可能被忽略
            # 同时发送 "required"（OpenAI 格式），代理层应自行翻译
            payload["tool_choice"] = effective_choice

        logger.info(
            f"[OpenAI-Stream] request model={self.model} msgs={len(messages)} "
            f"tools={len(tools or []) if not skip_tools else 0} "
            f"tool_choice={payload.get('tool_choice', 'N/A')} (requested={tool_choice})"
        )

        tool_calls_accum: dict[int, dict] = {}  # index → {id, name, arguments_str}
        in_thinking = False
        thinking_text = ""
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=False) as c:
                async with c.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        error_text = body.decode(errors="replace")[:500]
                        logger.error(f"[OpenAI-Stream] {resp.status_code}: {error_text}")
                        # 模型降级：stream+tools 失败
                        if tools and not skip_tools and "invalid" in error_text.lower():
                            _MODELS_NO_TOOLS_STREAM.add(self.model)
                            logger.warning(f"[OpenAI-Stream] 标记模型 {self.model} 不支持 stream+tools，重试")
                            async for chunk in self.chat_stream_with_tools(
                                messages, tools=None, temperature=temperature, max_tokens=max_tokens,
                                top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                            ):
                                yield chunk
                            return
                        resp.raise_for_status()

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # usage 统计
                        usage = chunk_data.get("usage")
                        if usage:
                            total_input_tokens = usage.get("prompt_tokens", total_input_tokens)
                            total_output_tokens = usage.get("completion_tokens", total_output_tokens)

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        finish = choices[0].get("finish_reason")

                        # Thinking / Reasoning 支持
                        reasoning = delta.get("reasoning_content") or delta.get("thinking") or ""
                        if reasoning:
                            if not in_thinking:
                                in_thinking = True
                            thinking_text += reasoning
                            yield LLMStreamChunk(thinking=reasoning)
                            continue

                        # 正文内容
                        content = delta.get("content", "")
                        if content:
                            if in_thinking:
                                in_thinking = False
                            yield LLMStreamChunk(text=content)

                        # tool_calls 累积
                        tc_deltas = delta.get("tool_calls", [])
                        for tc_delta in tc_deltas:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_accum:
                                tool_calls_accum[idx] = {
                                    "id": tc_delta.get("id", ""),
                                    "name": "",
                                    "arguments_str": "",
                                }
                            if tc_delta.get("id"):
                                tool_calls_accum[idx]["id"] = tc_delta["id"]
                            fn = tc_delta.get("function", {})
                            if fn.get("name"):
                                tool_calls_accum[idx]["name"] = fn["name"]
                            if fn.get("arguments"):
                                tool_calls_accum[idx]["arguments_str"] += fn["arguments"]

                        # 完成
                        if finish:
                            parsed_calls: list[ToolCall] = []
                            for idx in sorted(tool_calls_accum):
                                tc_info = tool_calls_accum[idx]
                                try:
                                    args = json.loads(tc_info["arguments_str"]) if tc_info["arguments_str"] else {}
                                except json.JSONDecodeError:
                                    args = {"raw": tc_info["arguments_str"]}
                                parsed_calls.append(ToolCall(
                                    id=tc_info["id"],
                                    name=tc_info["name"],
                                    arguments=args,
                                ))

                            logger.info(
                                f"[OpenAI-Stream] done: tool_calls={len(parsed_calls)} "
                                f"finish={finish} tool_choice_was={payload.get('tool_choice', 'N/A')}"
                            )
                            yield LLMStreamChunk(
                                is_done=True,
                                finish_reason=finish,
                                input_tokens=total_input_tokens,
                                output_tokens=total_output_tokens,
                                tool_calls=parsed_calls if parsed_calls else None,
                                thinking=thinking_text if thinking_text else None,
                            )
                            return

        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error(f"[OpenAI-Stream] error: {e}")
            # 降级：stream+tools 失败 → 标记并重试
            if tools and not skip_tools:
                _MODELS_NO_TOOLS_STREAM.add(self.model)
                logger.warning(f"[OpenAI-Stream] 降级: {self.model} stream+tools 失败，重试无 tools")
                async for chunk in self.chat_stream_with_tools(
                    messages, tools=None, temperature=temperature, max_tokens=max_tokens,
                    top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                ):
                    yield chunk
                return
            raise

        # 如果流正常结束但没有 finish_reason（兜底）
        if tool_calls_accum:
            parsed_calls = []
            for idx in sorted(tool_calls_accum):
                tc_info = tool_calls_accum[idx]
                try:
                    args = json.loads(tc_info["arguments_str"]) if tc_info["arguments_str"] else {}
                except json.JSONDecodeError:
                    args = {"raw": tc_info["arguments_str"]}
                parsed_calls.append(ToolCall(id=tc_info["id"], name=tc_info["name"], arguments=args))
            yield LLMStreamChunk(is_done=True, tool_calls=parsed_calls)
        else:
            yield LLMStreamChunk(is_done=True)

    # ─────────── 流式文字输出（无工具，保留向后兼容） ───────────

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> AsyncIterator[str]:
        """流式输出，逐 token yield 文本片段（不支持 tool_use）"""
        async for chunk in self.chat_stream_with_tools(
            messages=messages, tools=None,
            temperature=temperature, max_tokens=max_tokens,
            top_p=top_p, frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
        ):
            if chunk.text:
                yield chunk.text

    # ─────────── 简单文字调用（兼容旧接口） ───────────

    async def simple_chat(self, messages: list[dict]) -> str:
        """兼容 SouthgridLLMClient.chat() 接口，返回纯文字"""
        result = await self.chat(messages)
        return result.content or ""
