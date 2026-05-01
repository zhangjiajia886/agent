import re
import httpx
from typing import Optional, Dict, Any, AsyncIterator
from loguru import logger
from app.config import settings

def _filter_emotion_tags(text: str) -> str:
    """清除方括号 [xxx] 和英文圆括号 (xxx) 情感标记，防止 TTS 朗读出来。"""
    text = re.sub(r'\[[^\]]{1,40}\]', '', text)
    text = re.sub(r'\([a-zA-Z][a-zA-Z\s]{0,30}\)', '', text)
    return text


class FishSpeechClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FISH_API_KEY
        self.base_url = settings.FISH_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def synthesize_speech(
        self,
        text: str,
        reference_id: Optional[str] = None,
        format: str = "mp3",
        latency: str = "balanced",
        streaming: bool = False,
        tts_model: Optional[str] = None,
        normalize: bool = True,
        style_prompt: str = "",
        **kwargs
    ) -> bytes:
        url = f"{self.base_url}/v1/tts"
        model = tts_model or settings.FISH_TTS_MODEL
        clean_text = _filter_emotion_tags(text)
        final_text = f"[{style_prompt}] {clean_text}" if style_prompt else clean_text
        payload = {
            "text": final_text,
            "reference_id": reference_id or settings.FISH_DEFAULT_VOICE,
            "format": format,
            "latency": latency,
            "streaming": streaming,
            "normalize": normalize,
            **kwargs
        }
        
        tts_headers = {**self.headers, "model": model}
        logger.info(f"[TTS] model={model} text={payload['text'][:120]!r}")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=tts_headers)
                logger.info(f"[TTS] response status={response.status_code} size={len(response.content)} bytes")
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech TTS error: {e}")
            raise
    
    async def synthesize_speech_stream(
        self,
        text: str,
        reference_id: Optional[str] = None,
        format: str = "mp3",
        latency: str = "balanced",
        **kwargs
    ) -> AsyncIterator[bytes]:
        url = f"{self.base_url}/v1/tts"
        payload = {
            "text": _filter_emotion_tags(text),
            "reference_id": reference_id or settings.FISH_DEFAULT_VOICE,
            "format": format,
            "latency": latency,
            "streaming": True,
            "normalize": True,
            **kwargs
        }
        
        tts_headers = {**self.headers, "model": settings.FISH_TTS_MODEL}
        logger.info(f"[TTS-stream] model={settings.FISH_TTS_MODEL} text={payload['text'][:120]!r}")
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload, headers=tts_headers) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech TTS stream error: {e}")
            raise
    
    async def recognize_speech(
        self,
        audio_data: bytes,
        language: str = "zh",
        ignore_timestamps: bool = False,
        filename: str = "audio.mp3",
        content_type: str = "audio/mpeg",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/asr"
        files = {"audio": (filename, audio_data, content_type)}
        data = {
            "language": language,
            "ignore_timestamps": str(ignore_timestamps).lower(),
        }
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, files=files, data=data, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech ASR error: {e}")
            raise
    
    async def create_voice_model(
        self,
        title: str,
        audio_files: list,
        description: Optional[str] = None,
        visibility: str = "private",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/model"
        data = {
            "title": title,
            "description": description or "",
            "visibility": visibility,
            "type": "tts",
            "train_mode": "fast",
        }
        files = []
        for i, audio in enumerate(audio_files):
            if isinstance(audio, dict):
                fname = audio.get("filename") or f"sample_{i}.wav"
                content = audio["content"]
                ctype = audio.get("content_type") or "audio/wav"
            else:
                fname = f"sample_{i}.wav"
                content = audio
                ctype = "audio/wav"
            files.append(("voices", (fname, content, ctype)))

        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, data=data, files=files, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Fish Speech create model error: HTTP {e.response.status_code} - {e.response.text}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech create model error: {e}")
            raise
    
    async def get_voice_models(
        self,
        self_only: bool = True,
        page_size: int = 20,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/model"
        params = {
            "self": str(self_only).lower(),
            "page_size": page_size,
            "page_number": page_number,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech get models error: {e}")
            raise

    async def search_public_models(
        self,
        title: str = "",
        tag: str = "",
        page_size: int = 20,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/model"
        params: Dict[str, Any] = {
            "self": "false",
            "page_size": page_size,
            "page_number": page_number,
        }
        if title:
            params["title"] = title
        if tag:
            params["tag"] = tag
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Fish Speech search public models HTTP {e.response.status_code}: {e.response.text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Fish Speech search public models error [{type(e).__name__}]: {e}")
            raise
    
    async def get_voice_model_detail(self, model_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/model/{model_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech get model detail error: {e}")
            raise

    async def delete_voice_model(self, model_id: str) -> bool:
        url = f"{self.base_url}/model/{model_id}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self.headers)
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech delete model error: {e}")
            return False
    
    async def get_api_credit(self) -> Dict[str, Any]:
        url = f"{self.base_url}/wallet/self/api-credit"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Fish Speech get credit error: {e}")
            raise


fish_client = FishSpeechClient()
