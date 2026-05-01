from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Any
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Models discovered at runtime to not support tools in streaming mode.
# Populated automatically on first 400 failure; persists for the process lifetime.
_MODELS_NO_TOOLS_STREAM: set[str] = set()


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    tool_calls: list[dict] | None = None


@dataclass
class LLMStreamChunk:
    text: str = ""
    is_done: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""
    tool_calls: list[dict] | None = None


class LLMClient:
    """
    Unified LLM client supporting:
    - southgrid: 南网推理平台 (HMAC-SHA256 auth, httpx direct)
    - openai:    OpenAI-compatible APIs (litellm)
    - ollama:    Ollama local (litellm)
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        provider: str = "openai",
        custcode: str = "",
        componentcode: str = "",
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.provider = provider
        self.custcode = custcode
        self.componentcode = componentcode

    async def _resolve_model_config(self, model: str) -> tuple[str, str, str, str, str]:
        """
        Look up model-specific config from DB.
        Returns (provider, base_url, api_key, custcode, componentcode).
        Falls back to self defaults if model not found in DB.
        """
        try:
            from ..db.database import get_db
            import json as _json
            db = await get_db()
            row = await db.execute(
                "SELECT provider, api_base, api_key_ref, config FROM model_configs WHERE model_id = ?",
                (model,),
            )
            rec = await row.fetchone()
            if not rec:
                row = await db.execute(
                    "SELECT provider, api_base, api_key_ref, config FROM model_configs WHERE LOWER(model_id) = LOWER(?)",
                    (model,),
                )
                rec = await row.fetchone()
            if not rec:
                # Fallback: match by DB record id (e.g. "aipro_claude_sonnet_4_6")
                row = await db.execute(
                    "SELECT provider, api_base, api_key_ref, config FROM model_configs WHERE id = ?",
                    (model,),
                )
                rec = await row.fetchone()
            if rec:
                cfg = _json.loads(rec["config"]) if rec["config"] else {}
                logger.info(f"Resolved model {model!r} → provider={rec['provider']!r} base={rec['api_base']!r}")
                return (
                    rec["provider"] or self.provider,
                    rec["api_base"] or self.base_url,
                    rec["api_key_ref"] or self.api_key,
                    cfg.get("custCode", self.custcode),
                    cfg.get("componentCode", self.componentcode),
                )
            # Dump registered models for diagnosis
            all_rows = await db.execute("SELECT id, model_id, provider, api_base, api_key_ref FROM model_configs")
            all_models = await all_rows.fetchall()
            logger.warning(
                f"Model {model!r} not found in model_configs. "
                f"Registered: {[(r['id'], r['model_id'], r['provider']) for r in all_models]}"
            )
            # Last-resort: if default provider is southgrid (likely unavailable) and there
            # is any openai-compatible config registered, use that instead of ConnectError.
            if self.provider == "southgrid":
                for r in all_models:
                    if r["provider"] == "openai" and r["api_base"] and r["api_key_ref"]:
                        logger.warning(
                            f"Southgrid default unavailable, using openai fallback: "
                            f"id={r['id']!r} base={r['api_base']!r}"
                        )
                        return "openai", r["api_base"], r["api_key_ref"], "", ""
        except Exception as e:
            logger.warning(f"Failed to resolve model config for {model!r}: {e!r}")
        logger.warning(f"Falling back to default provider={self.provider!r} for model={model!r}")
        return self.provider, self.base_url, self.api_key, self.custcode, self.componentcode

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        enable_thinking: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[LLMStreamChunk]:
        # Resolve per-model config (may switch provider for aipro/openai models)
        provider, base_url, api_key, custcode, componentcode = await self._resolve_model_config(model)
        logger.info(f"LLM call: provider={provider}, model={model}, stream={stream}, thinking={enable_thinking}")

        if provider == "southgrid":
            if stream:
                return self._southgrid_stream(model, messages, tools, temperature, max_tokens,
                                              base_url=base_url, api_key=api_key,
                                              custcode=custcode, componentcode=componentcode)
            else:
                return await self._southgrid_chat(model, messages, tools, temperature, max_tokens,
                                                  base_url=base_url, api_key=api_key,
                                                  custcode=custcode, componentcode=componentcode)
        else:
            # openai / aipro / ollama — all go through litellm with resolved base_url & api_key
            return await self._litellm_chat(model, messages, tools, temperature, max_tokens, stream,
                                            base_url=base_url, api_key=api_key, provider=provider,
                                            enable_thinking=enable_thinking)

    # ── southgrid: httpx direct with HMAC auth ──

    def _build_southgrid_payload(
        self, model: str, messages: list[dict], tools: list[dict] | None,
        temperature: float, max_tokens: int, stream: bool,
        componentcode: str = "",
    ) -> dict:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "componentCode": componentcode or self.componentcode,
        }
        # Qwen3 supports thinking mode via enable_thinking flag
        if "qwen3" in model.lower():
            payload["enable_thinking"] = True
        # NOTE: southgrid gateway does not support OpenAI tools/function calling.
        # tools parameter is intentionally omitted.
        return payload

    def _build_southgrid_headers(self, custcode: str = "", api_key: str = "") -> dict[str, str]:
        from .southgrid_auth import build_auth_headers
        return build_auth_headers(custcode or self.custcode, api_key or self.api_key)

    async def _southgrid_chat(
        self, model: str, messages: list[dict], tools: list[dict] | None,
        temperature: float, max_tokens: int,
        base_url: str = "", api_key: str = "", custcode: str = "", componentcode: str = "",
    ) -> LLMResponse:
        headers = self._build_southgrid_headers(custcode, api_key)
        payload = self._build_southgrid_payload(model, messages, tools, temperature, max_tokens, stream=False, componentcode=componentcode)
        url = base_url or self.base_url

        async with httpx.AsyncClient(verify=False, timeout=120) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage = data.get("usage", {})

        tc = None
        if msg.get("tool_calls"):
            tc = [
                {
                    "id": t.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": t.get("function", {}).get("name", ""),
                        "arguments": t.get("function", {}).get("arguments", ""),
                    },
                }
                for t in msg["tool_calls"]
            ]

        return LLMResponse(
            text=msg.get("content", "") or "",
            model=model,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", ""),
            tool_calls=tc,
        )

    async def _southgrid_stream(
        self, model: str, messages: list[dict], tools: list[dict] | None,
        temperature: float, max_tokens: int,
        base_url: str = "", api_key: str = "", custcode: str = "", componentcode: str = "",
    ) -> AsyncIterator[LLMStreamChunk]:
        headers = self._build_southgrid_headers(custcode, api_key)
        payload = self._build_southgrid_payload(model, messages, tools, temperature, max_tokens, stream=True, componentcode=componentcode)
        url = base_url or self.base_url

        tool_calls_accum: dict[int, dict] = {}
        _in_thinking = False  # track open <think> block

        logger.info(f"southgrid stream: model={model}, componentCode={componentcode or self.componentcode}, url={url}")

        async with httpx.AsyncClient(verify=False, timeout=120) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error(f"southgrid API {resp.status_code}: {body.decode('utf-8', errors='replace')}")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        if _in_thinking:
                            yield LLMStreamChunk(text="</think>")
                        # Yield final chunk if we have accumulated tool_calls
                        if tool_calls_accum:
                            final_tc = [tool_calls_accum[i] for i in sorted(tool_calls_accum.keys())]
                            yield LLMStreamChunk(is_done=True, finish_reason="stop", tool_calls=final_tc)
                        else:
                            yield LLMStreamChunk(is_done=True, finish_reason="stop")
                        return

                    try:
                        chunk_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk_data.get("choices", [])
                    if not choices:
                        continue

                    choice = choices[0]
                    delta = choice.get("delta", {})

                    # Thinking content (Qwen3 via southgrid uses reasoning_content field)
                    reasoning = delta.get("reasoning_content", "") or delta.get("thinking", "")
                    content = delta.get("content", "")
                    if reasoning:
                        if not _in_thinking:
                            _in_thinking = True
                            yield LLMStreamChunk(text="<think>")
                        yield LLMStreamChunk(text=reasoning)
                    if content:
                        if _in_thinking:
                            _in_thinking = False
                            yield LLMStreamChunk(text="</think>")
                        yield LLMStreamChunk(text=content)

                    # Tool calls accumulation
                    if delta.get("tool_calls"):
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_accum:
                                tool_calls_accum[idx] = {
                                    "id": tc_delta.get("id", "") or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            acc = tool_calls_accum[idx]
                            if tc_delta.get("id"):
                                acc["id"] = tc_delta["id"]
                            func = tc_delta.get("function", {})
                            if func.get("name"):
                                acc["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                acc["function"]["arguments"] += func["arguments"]

                    # Finish reason
                    finish = choice.get("finish_reason")
                    if finish:
                        usage = chunk_data.get("usage", {})
                        final_tc = None
                        if tool_calls_accum:
                            final_tc = [tool_calls_accum[i] for i in sorted(tool_calls_accum.keys())]
                        yield LLMStreamChunk(
                            is_done=True,
                            finish_reason=finish,
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                            tool_calls=final_tc,
                        )

    # ── OpenAI-compatible provider (AIPro / OpenAI) via direct openai client ──

    async def _openai_compat_stream(
        self, model: str, messages: list[dict], tools: list[dict] | None,
        temperature: float, max_tokens: int,
        base_url: str, api_key: str, extra_body: dict | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key or "sk-placeholder", base_url=base_url)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # Skip tools for models already known to not support them in streaming mode
        if tools and model not in _MODELS_NO_TOOLS_STREAM:
            kwargs["tools"] = tools
        if extra_body:
            kwargs["extra_body"] = extra_body

        tool_calls_accum: dict[int, dict] = {}
        _in_thinking = False  # track if we are mid <thinking> block
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            # Some AIPro models (e.g. claude-opus-4-6, gemini-3-flash-preview) reject
            # streaming requests that include tools (invalid_request_error or
            # bad_response_status_code).  Retry once without tools so the model
            # can at least answer as a plain chat model.
            err_str = str(e)
            if kwargs.get("tools") and (
                "invalid_request_error" in err_str or "bad_response_status_code" in err_str
            ):
                _MODELS_NO_TOOLS_STREAM.add(model)
                logger.warning(
                    f"[LLM] Model {model!r} rejected stream+tools ({err_str[:80]}). "
                    "Marked as no-tools-stream; retrying without tools."
                )
                kwargs.pop("tools")
                response = await client.chat.completions.create(**kwargs)
            else:
                raise
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta:
                # Capture thinking/reasoning field (AIPro / DeepSeek-style proxy)
                reasoning = (
                    getattr(delta, "reasoning_content", None)
                    or getattr(delta, "thinking", None)
                )
                text = delta.content or ""
                if reasoning:
                    if not _in_thinking:
                        _in_thinking = True
                        yield LLMStreamChunk(text="<thinking>")
                    yield LLMStreamChunk(text=reasoning)
                if text:
                    if _in_thinking:
                        _in_thinking = False
                        yield LLMStreamChunk(text="</thinking>")
                    yield LLMStreamChunk(text=text)
            if delta and getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = getattr(tc_delta, "index", 0)
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {
                            "id": getattr(tc_delta, "id", "") or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = tool_calls_accum[idx]
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if getattr(tc_delta, "function", None):
                        if tc_delta.function.name:
                            acc["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            acc["function"]["arguments"] += tc_delta.function.arguments
            if chunk.choices and chunk.choices[0].finish_reason:
                if _in_thinking:
                    yield LLMStreamChunk(text="</thinking>")
                    _in_thinking = False
                usage = getattr(chunk, "usage", None)
                final_tc = [tool_calls_accum[i] for i in sorted(tool_calls_accum)] or None
                yield LLMStreamChunk(
                    is_done=True,
                    finish_reason=chunk.choices[0].finish_reason,
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    tool_calls=final_tc,
                )

    # ── litellm fallback for ollama ──

    async def _litellm_chat(
        self, model: str, messages: list[dict], tools: list[dict] | None,
        temperature: float, max_tokens: int, stream: bool,
        base_url: str = "", api_key: str = "", provider: str = "",
        enable_thinking: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMStreamChunk]:
        import litellm

        effective_provider = provider or self.provider
        effective_base_url = base_url or self.base_url
        effective_api_key = api_key or self.api_key

        # Claude / OpenAI extended thinking:
        # - AIPro proxy: use model name ending in "-thinking" (e.g. claude-opus-4-6-thinking).
        #   The proxy enables thinking internally; it does NOT accept extra_body or temp=1 override.
        # - Native Anthropic API: use extra_body + temperature=1.
        # - enable_thinking flag ONLY affects native Anthropic API calls.
        _is_native_anthropic = not effective_base_url or "anthropic.com" in effective_base_url
        extra_body: dict | None = None
        eff_temperature = temperature
        # temperature=1 required only for native Anthropic thinking or "-thinking" suffix models
        if model.endswith("-thinking") or (enable_thinking and _is_native_anthropic):
            eff_temperature = 1
        # extra_body only for native Anthropic API; proxies ignore/reject it
        if enable_thinking and not model.endswith("-thinking") and _is_native_anthropic:
            extra_body = {"thinking": {"type": "enabled", "budget_tokens": min(max_tokens // 2, 8000)}}

        # OpenAI-compatible providers (AIPro, plain OpenAI): use openai client directly
        # for reliable streaming — litellm can buffer or stall with custom api_base
        if effective_provider != "ollama":
            if stream:
                return self._openai_compat_stream(
                    model, messages, tools, eff_temperature, max_tokens,
                    effective_base_url, effective_api_key, extra_body,
                )
            else:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=effective_api_key or "sk-placeholder",
                                     base_url=effective_base_url)
                kwargs: dict[str, Any] = {
                    "model": model, "messages": messages,
                    "temperature": eff_temperature, "max_tokens": max_tokens,
                }
                if tools:
                    kwargs["tools"] = tools
                if extra_body:
                    kwargs["extra_body"] = extra_body
                response = await client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                usage = response.usage
                tc = None
                if choice.message.tool_calls:
                    tc = [{"id": t.id, "type": "function",
                           "function": {"name": t.function.name, "arguments": t.function.arguments}}
                          for t in choice.message.tool_calls]
                return LLMResponse(
                    text=choice.message.content or "",
                    model=model,
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    finish_reason=choice.finish_reason or "",
                    tool_calls=tc,
                )

        # Ollama via litellm
        model_name = f"ollama/{model}" if "/" not in model else model
        call_kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": eff_temperature,
            "max_tokens": max_tokens,
            "api_base": effective_base_url,
            "api_key": effective_api_key or "sk-placeholder",
            "stream": stream,
        }
        if tools:
            call_kwargs["tools"] = tools

        if stream:
            return self._litellm_stream(call_kwargs)
        else:
            response = await litellm.acompletion(**call_kwargs)
            choice = response.choices[0]
            usage = response.usage or {}
            tc = None
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                tc = [{"id": t.id, "type": "function",
                       "function": {"name": t.function.name, "arguments": t.function.arguments}}
                      for t in choice.message.tool_calls]
            return LLMResponse(
                text=choice.message.content or "",
                model=model,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
                finish_reason=choice.finish_reason or "",
                tool_calls=tc,
            )

    async def _litellm_stream(self, call_kwargs: dict) -> AsyncIterator[LLMStreamChunk]:
        import litellm
        response = await litellm.acompletion(**call_kwargs)
        tool_calls_accum: dict[int, dict] = {}
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield LLMStreamChunk(text=delta.content)
            if delta and hasattr(delta, "tool_calls") and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index if hasattr(tc_delta, "index") else 0
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {
                            "id": getattr(tc_delta, "id", "") or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = tool_calls_accum[idx]
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if hasattr(tc_delta, "function") and tc_delta.function:
                        if tc_delta.function.name:
                            acc["function"]["name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            acc["function"]["arguments"] += tc_delta.function.arguments
            if chunk.choices and chunk.choices[0].finish_reason:
                usage = getattr(chunk, "usage", None)
                final_tc = None
                if tool_calls_accum:
                    final_tc = [tool_calls_accum[i] for i in sorted(tool_calls_accum.keys())]
                yield LLMStreamChunk(
                    is_done=True,
                    finish_reason=chunk.choices[0].finish_reason,
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    tool_calls=final_tc,
                )

    async def list_models(self) -> list[dict]:
        """List configured models from settings."""
        from ..core.config import get_settings
        settings = get_settings()
        profiles = settings.get_model_profiles()
        result = []
        for role, profile in profiles.items():
            result.append({
                "id": profile.model,
                "name": profile.model,
                "role": role,
                "provider": profile.provider,
                "base_url": profile.base_url,
            })
        return result
