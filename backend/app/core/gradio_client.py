"""Gradio Space 通用调用基类，异步封装同步 gradio_client SDK"""

import asyncio
import os
import tempfile
import time
from typing import Optional, Any
from gradio_client import Client, handle_file
from loguru import logger
from app.config import settings


class GradioSpaceClient:

    def _describe_result(self, result: Any) -> str:
        if isinstance(result, dict):
            return f"dict(keys={list(result.keys())})"
        if isinstance(result, (list, tuple)):
            items = ", ".join(self._describe_result(i) for i in result)
            return f"{type(result).__name__}(len={len(result)})[{items}]"
        return type(result).__name__

    def __init__(self, space_id: str, timeout: Optional[int] = None):
        self.space_id = space_id
        self.timeout = timeout or settings.SOUL_API_TIMEOUT
        self.hf_token = settings.SOUL_HF_TOKEN or None
        self._client: Optional[Client] = None

    def _should_retry_client_init(self, error: Exception) -> bool:
        error_text = str(error).lower()
        retry_markers = (
            "handshake operation timed out",
            "ssl",
            "timed out",
            "connection aborted",
            "connection reset",
            "temporarily unavailable",
        )
        return any(marker in error_text for marker in retry_markers)

    def _get_client(self) -> Client:
        if self._client is not None:
            return self._client
        if self.hf_token:
            os.environ["HF_TOKEN"] = self.hf_token
            os.environ["HUGGINGFACEHUB_API_TOKEN"] = self.hf_token
            logger.info(f"已为 Gradio Space 注入 Hugging Face Token space={self.space_id}")
        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                logger.info(f"正在初始化 Gradio 客户端 space={self.space_id} attempt={attempt}/3")
                self._client = Client(self.space_id)
                return self._client
            except Exception as error:
                last_error = error
                self._client = None
                if attempt >= 3 or not self._should_retry_client_init(error):
                    raise
                logger.warning(
                    f"Gradio 客户端初始化失败，准备重试 space={self.space_id} attempt={attempt}/3 错误={error}"
                )
                time.sleep(attempt)
        raise last_error or RuntimeError(f"初始化 Gradio 客户端失败 space={self.space_id}")

    async def save_temp_file(self, data: bytes, suffix: str) -> str:
        """将 bytes 写入临时文件，返回路径"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, data)
        os.close(fd)
        return path

    async def call(self, api_name: str, **kwargs) -> Any:
        """在线程池中执行同步 Gradio 调用，不阻塞事件循环"""
        loop = asyncio.get_event_loop()

        def _sync():
            client = self._get_client()
            return client.predict(api_name=api_name, **kwargs)

        logger.info(
            f"开始同步调用 Gradio 接口 space={self.space_id} api={api_name} 参数键={list(kwargs.keys())}"
        )
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _sync),
            timeout=self.timeout,
        )
        logger.info(
            f"同步调用 Gradio 接口完成 space={self.space_id} api={api_name} 返回结构={self._describe_result(result)}"
        )
        return result

    async def submit(self, api_name: str, **kwargs) -> Any:
        """在线程池中执行队列式 Gradio 调用，适合长时或流式任务"""
        loop = asyncio.get_event_loop()

        def _sync():
            client = self._get_client()
            job = client.submit(api_name=api_name, **kwargs)
            return job.result()

        logger.info(
            f"开始提交 Gradio 队列任务 space={self.space_id} api={api_name} 参数键={list(kwargs.keys())} 超时时间={self.timeout}秒"
        )
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _sync),
            timeout=self.timeout,
        )
        logger.info(
            f"Gradio 队列任务执行完成 space={self.space_id} api={api_name} 返回结构={self._describe_result(result)}"
        )
        return result

    def _resolve_result_filepath(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            for key in ("path", "name", "file", "filepath", "video", "audio"):
                value = result.get(key)
                if value is None:
                    continue
                if isinstance(value, str):
                    return value
                try:
                    return self._resolve_result_filepath(value)
                except ValueError:
                    continue
        if isinstance(result, (list, tuple)) and result:
            for item in reversed(result):
                try:
                    return self._resolve_result_filepath(item)
                except ValueError:
                    continue
        raise ValueError(
            f"Unsupported gradio result payload: {self._describe_result(result)}"
        )

    async def read_result_file(self, filepath: str) -> bytes:
        """读取 Gradio 返回的本地文件路径为 bytes"""
        loop = asyncio.get_event_loop()
        resolved_path = self._resolve_result_filepath(filepath)
        logger.info(
            f"Gradio 结果文件路径解析完成 原始结构={self._describe_result(filepath)} 解析路径={resolved_path}"
        )
        def _read():
            with open(resolved_path, "rb") as f:
                return f.read()
        return await loop.run_in_executor(None, _read)

    async def health_check(self) -> bool:
        """检查 Space 是否在线"""
        try:
            loop = asyncio.get_event_loop()
            def _check():
                client = self._get_client()
                return client.view_api()  # 不报错即在线
            logger.info(f"开始检查 Gradio Space 健康状态 space={self.space_id}")
            await asyncio.wait_for(
                loop.run_in_executor(None, _check),
                timeout=30,
            )
            logger.info(f"Gradio Space 健康检查通过 space={self.space_id}")
            return True
        except Exception as e:
            logger.warning(f"Gradio Space 健康检查失败 space={self.space_id} 错误={e}")
            return False
