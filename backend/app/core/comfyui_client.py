import uuid
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from app.config import settings


class ComfyUIClient:
    """ComfyUI HTTP API 客户端，对接 AutoDL 实例上的 ComfyUI 服务"""

    def __init__(self):
        self.base_url = settings.COMFYUI_URL.rstrip("/")
        self.timeout = settings.COMFYUI_TIMEOUT
        self._client_id = str(uuid.uuid4())

    # ─────────────────── 基础接口 ───────────────────

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=10, verify=False) as c:
            try:
                r = await c.get(f"{self.base_url}/system_stats")
                return r.status_code == 200
            except Exception as e:
                logger.warning(f"ComfyUI health check failed: {e}")
                return False

    async def upload_image(self, image_bytes: bytes, filename: str = "input.jpg") -> str:
        async with httpx.AsyncClient(timeout=30, verify=False) as c:
            r = await c.post(
                f"{self.base_url}/upload/image",
                files={"image": (filename, image_bytes, "image/jpeg")},
            )
            r.raise_for_status()
            return r.json()["name"]

    async def submit_workflow(self, workflow: dict) -> str:
        clean = {k: v for k, v in workflow.items() if not k.startswith("__")}
        payload = {"prompt": clean, "client_id": self._client_id}
        async with httpx.AsyncClient(timeout=30, verify=False) as c:
            r = await c.post(f"{self.base_url}/prompt", json=payload)
            if r.status_code != 200:
                try:
                    body = r.json()
                    err_msg = body.get("error", {}).get("message", "")
                    node_errors = body.get("node_errors", {})
                    details = "; ".join(
                        f"{nid}({nd.get('class_type','')}): {[e['details'] for e in nd.get('errors',[])]}"
                        for nid, nd in node_errors.items()
                    )
                    raise RuntimeError(f"ComfyUI {r.status_code}: {err_msg} | {details}")
                except RuntimeError:
                    raise
                except Exception:
                    r.raise_for_status()
            result = r.json()
            if "error" in result:
                raise RuntimeError(f"ComfyUI 工作流提交失败: {result['error']}")
            if result.get("node_errors"):
                raise RuntimeError(f"ComfyUI 节点错误: {result['node_errors']}")
            return result["prompt_id"]

    async def wait_result(self, prompt_id: str, poll_interval: float = 2.0) -> dict:
        deadline = time.time() + self.timeout
        async with httpx.AsyncClient(timeout=10, verify=False) as c:
            while time.time() < deadline:
                r = await c.get(f"{self.base_url}/history/{prompt_id}")
                data = r.json()
                if prompt_id in data:
                    return data[prompt_id]["outputs"]
                await asyncio.sleep(poll_interval)
        raise TimeoutError(f"ComfyUI 超时（{self.timeout}s），prompt_id={prompt_id}")

    async def download_output(self, filename: str) -> bytes:
        async with httpx.AsyncClient(timeout=60, verify=False) as c:
            r = await c.get(
                f"{self.base_url}/view",
                params={"filename": filename, "type": "output"},
            )
            r.raise_for_status()
            return r.content

    # ─────────────────── 高层接口 ───────────────────

    async def run_workflow(self, workflow: dict) -> bytes:
        """提交工作流 → 等待完成 → 返回第一张输出图像的 bytes"""
        prompt_id = await self.submit_workflow(workflow)
        logger.debug(f"ComfyUI workflow submitted: {prompt_id[:8]}")
        outputs = await self.wait_result(prompt_id)
        for node_output in outputs.values():
            if "images" in node_output:
                filename = node_output["images"][0]["filename"]
                return await self.download_output(filename)
        raise RuntimeError("ComfyUI 未返回图像输出")

    async def run_workflow_video(self, workflow: dict) -> bytes:
        """提交工作流 → 等待完成 → 返回第一个视频的 bytes"""
        prompt_id = await self.submit_workflow(workflow)
        outputs = await self.wait_result(prompt_id)
        for node_output in outputs.values():
            if "videos" in node_output:
                filename = node_output["videos"][0]["filename"]
                return await self.download_output(filename)
            if "gifs" in node_output:
                filename = node_output["gifs"][0]["filename"]
                return await self.download_output(filename)
        raise RuntimeError("ComfyUI 未返回视频输出")


comfyui_client = ComfyUIClient()
