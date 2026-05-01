"""SoulX-Podcast 播客语音合成客户端

当 settings.SOUL_PODCAST_URL 非空时，调用自托管 FastAPI REST 服务；
否则回退到 HuggingFace Gradio Space。
"""

import json
import os
from typing import Optional
import httpx
from gradio_client import handle_file
from loguru import logger
from app.config import settings
from app.core.gradio_client import GradioSpaceClient


class PodcastClient(GradioSpaceClient):

    def __init__(self):
        super().__init__(settings.SOUL_PODCAST_SPACE)
        self._rest_base_url = (settings.SOUL_PODCAST_URL or "").rstrip("/")

    def _use_rest(self) -> bool:
        return bool(self._rest_base_url)

    async def _synthesize_rest(
        self,
        target_text: str,
        spk1_prompt_audio_bytes: bytes,
        spk1_prompt_text: str,
        spk2_prompt_audio_bytes: Optional[bytes],
        spk2_prompt_text: str,
        seed: int,
    ) -> bytes:
        """调用自托管 FastAPI /generate 端点"""
        files = [("prompt_audio", ("spk1.wav", spk1_prompt_audio_bytes, "audio/wav"))]
        prompt_texts = [spk1_prompt_text]
        if spk2_prompt_audio_bytes:
            files.append(("prompt_audio", ("spk2.wav", spk2_prompt_audio_bytes, "audio/wav")))
            prompt_texts.append(spk2_prompt_text)

        data = {
            "dialogue_text": target_text,
            "prompt_texts": json.dumps(prompt_texts, ensure_ascii=False),
            "seed": str(seed),
        }
        url = f"{self._rest_base_url}/generate"
        logger.info(f"调用自托管 Podcast REST API url={url} 说话人数={len(files)}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, data=data, files=files)
            resp.raise_for_status()
            return resp.content

    async def synthesize(
        self,
        target_text: str,
        spk1_prompt_audio_bytes: bytes,
        spk1_prompt_text: str = "",
        spk1_dialect_prompt_text: str = "",
        spk2_prompt_audio_bytes: Optional[bytes] = None,
        spk2_prompt_text: str = "",
        spk2_dialect_prompt_text: str = "",
        seed: int = 1988,
    ) -> bytes:
        """
        播客/对话语音合成（支持双说话人独立配置）

        :param target_text: 对话文本，格式 "[S1]xxx\n[S2]xxx"
                            支持 [S1]~[S4]，支持副语言标签 <|laughter|> <|sigh|> 等
        :param spk1_prompt_audio_bytes: 说话人1 参考音频（零样本声音克隆）
        :param spk1_prompt_text: 说话人1 参考文本（对应参考音频的文字内容）
        :param spk1_dialect_prompt_text: 说话人1 方言提示，如 "<|Sichuan|>四川话文本"
        :param spk2_prompt_audio_bytes: 说话人2 参考音频（可选，单人独白可不传）
        :param spk2_prompt_text: 说话人2 参考文本
        :param spk2_dialect_prompt_text: 说话人2 方言提示
        :param seed: 随机种子（控制生成一致性）
        :return: 合成音频 bytes (wav)
        """
        if self._use_rest():
            return await self._synthesize_rest(
                target_text=target_text,
                spk1_prompt_audio_bytes=spk1_prompt_audio_bytes,
                spk1_prompt_text=spk1_prompt_text,
                spk2_prompt_audio_bytes=spk2_prompt_audio_bytes,
                spk2_prompt_text=spk2_prompt_text,
                seed=seed,
            )

        spk1_path = await self.save_temp_file(spk1_prompt_audio_bytes, ".wav")
        spk2_path = None
        try:
            if spk2_prompt_audio_bytes:
                spk2_path = await self.save_temp_file(spk2_prompt_audio_bytes, ".wav")

            result = await self.call(
                api_name="/dialogue_synthesis_function",
                target_text=target_text,
                spk1_prompt_text=spk1_prompt_text,
                spk1_prompt_audio=handle_file(spk1_path),
                spk1_dialect_prompt_text=spk1_dialect_prompt_text,
                spk2_prompt_text=spk2_prompt_text,
                spk2_prompt_audio=handle_file(spk2_path) if spk2_path else None,
                spk2_dialect_prompt_text=spk2_dialect_prompt_text,
                seed=seed,
            )
            if isinstance(result, str):
                return await self.read_result_file(result)
            elif isinstance(result, tuple):
                return await self.read_result_file(result[0])
            return result
        finally:
            os.unlink(spk1_path)
            if spk2_path:
                os.unlink(spk2_path)


podcast_client = PodcastClient()
