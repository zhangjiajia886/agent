import json
import hmac
import hashlib
import base64
import email.utils
import httpx
from typing import AsyncIterator
from loguru import logger

from app.config import settings


class SouthgridLLMClient:
    """南方电网 AI 网关 LLM 客户端，使用 HMAC-SHA256 签名认证"""

    def __init__(self):
        self.base_url = settings.L1_LLM_BINDING_HOST
        self.secret_key = settings.L1_LLM_BINDING_API_KEY
        self.model = settings.L1_LLM_MODEL
        self.custcode = settings.L1_LLM_CUSTCODE
        self.componentcode = settings.L1_LLM_COMPONENTCODE

    def _build_headers(self) -> dict:
        x_date = email.utils.formatdate(usegmt=True)
        str_to_sign = f"x-date: {x_date}"
        h = hmac.new(
            self.secret_key.encode("utf-8"),
            str_to_sign.encode("utf-8"),
            hashlib.sha256,
        )
        signature = base64.b64encode(h.digest()).decode("utf-8")
        authorization = (
            f'hmac username="{self.custcode}", '
            f'algorithm="hmac-sha256", '
            f'headers="x-date", '
            f'signature="{signature}"'
        )
        return {
            "x-date": x_date,
            "authorization": authorization,
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages: list, stream: bool = True) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2048,
            "componentCode": self.componentcode,
        }

    async def chat_stream(self, messages: list) -> AsyncIterator[str]:
        """流式输出，逐 token yield 文本片段"""
        payload = self._build_payload(messages, stream=True)
        logger.debug(f"LLM stream request: model={self.model}, msgs={len(messages)}")

        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers=self._build_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def chat(self, messages: list) -> str:
        """非流式调用，返回完整回复"""
        payload = self._build_payload(messages, stream=False)
        logger.debug(f"LLM request: model={self.model}")

        async with httpx.AsyncClient(timeout=60, verify=False) as client:
            resp = await client.post(
                self.base_url,
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"LLM 响应格式异常: {str(data)[:300]}")
                raise RuntimeError(f"LLM 响应格式异常: {e}") from e
            # 剥离 <think>...</think> 包裹
            if "<think>" in content:
                import re
                content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()
            return content


llm_client = SouthgridLLMClient()
