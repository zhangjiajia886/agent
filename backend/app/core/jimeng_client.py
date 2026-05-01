import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx


@dataclass
class JimengTaskResult:
    status: str
    data: dict[str, Any]
    elapsed: float


class JimengProvider:
    def __init__(
        self,
        ak: str,
        sk: str,
        region: str = "cn-north-1",
        host: str = "visual.volcengineapi.com",
        timeout: int = 300,
    ):
        self.ak = ak
        self.sk = sk
        self.region = region
        self.host = host
        self.timeout = timeout
        self.service = "cv"
        self.content_type = "application/json;charset=utf-8"

    @property
    def enabled(self) -> bool:
        return bool(self.ak and self.sk)

    def _sign(self, method: str, path: str, query: dict[str, str], body: bytes) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_date = now.strftime("%Y%m%d")
        canonical_query = "&".join(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}"
            for k, v in sorted(query.items())
        )
        canonical_headers = f"content-type:{self.content_type}\nhost:{self.host}\nx-date:{x_date}\n"
        signed_headers = "content-type;host;x-date"
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_request = f"{method}\n{path}\n{canonical_query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        scope = f"{short_date}/{self.region}/{self.service}/request"
        string_to_sign = (
            f"HMAC-SHA256\n{x_date}\n{scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        def digest(key: bytes | str, message: str) -> bytes:
            return hmac.new(
                key if isinstance(key, bytes) else key.encode(),
                message.encode(),
                hashlib.sha256,
            ).digest()

        signing_key = digest(self.sk, short_date)
        signing_key = digest(signing_key, self.region)
        signing_key = digest(signing_key, self.service)
        signing_key = digest(signing_key, "request")
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return {
            "Authorization": f"HMAC-SHA256 Credential={self.ak}/{scope}, SignedHeaders={signed_headers}, Signature={signature}",
            "X-Date": x_date,
            "Host": self.host,
            "Content-Type": self.content_type,
        }

    def _post(self, action: str, version: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "error", "error": "JIMENG_AK/JIMENG_SK 未配置"}
        query = {"Action": action, "Version": version}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = self._sign("POST", "/", query, body)
        url = f"https://{self.host}/?Action={quote(action)}&Version={quote(version)}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, content=body)
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}
            if response.status_code >= 400:
                return {
                    "status": "error",
                    "http_status": response.status_code,
                    "error": self._classify_error(data),
                    "raw": data,
                }
            return data

    def _download_url(self, url: str) -> bytes:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    def _extract_media(self, data: dict[str, Any]) -> tuple[bytes | None, str]:
        payload = data.get("data") or data.get("Result") or data
        if not isinstance(payload, dict):
            return None, "none"
        for key in ("binary_data_base64", "binaryDataBase64"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                return base64.b64decode(value[0]), key
            if isinstance(value, str) and value:
                return base64.b64decode(value), key
        for key in ("image_urls", "imageUrls", "video_urls", "videoUrls", "url", "image_url", "video_url"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                return self._download_url(value[0]), key
            if isinstance(value, str) and value.startswith("http"):
                return self._download_url(value), key
        return None, "none"

    def _classify_error(self, data: dict[str, Any]) -> str:
        text = json.dumps(data, ensure_ascii=False)
        if "Access Denied" in text or "Unauthorized" in text or "50400" in text:
            return "权限或鉴权失败"
        if "quota" in text.lower() or "余额" in text or "额度" in text:
            return "配额或余额不足"
        if "parameter" in text.lower() or "参数" in text:
            return "参数错误"
        if "审核" in text or "sensitive" in text.lower():
            return "内容审核失败"
        return "接口调用失败"

    def legacy_generate_image(
        self,
        prompt: str,
        width: int = 768,
        height: int = 1024,
        seed: int = -1,
        req_key: str = "jimeng_high_aes_general_v21_L",
    ) -> dict[str, Any]:
        started = time.time()
        payload = {
            "req_key": req_key,
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "return_url": True,
        }
        data = self._post("CVProcess", "2022-08-31", payload)
        if data.get("status") == "error":
            return data
        if data.get("code") not in (None, 10000):
            return {"status": "error", "error": self._classify_error(data), "raw": data}
        media, source = self._extract_media(data)
        if not media:
            return {"status": "error", "error": "响应中没有可解析的媒体结果", "raw": data}
        return {
            "status": "success",
            "media_bytes": media,
            "media_ext": "png",
            "media_source": source,
            "provider": "jimeng",
            "capability": "legacy_image_generation",
            "model": req_key,
            "elapsed": round(time.time() - started, 2),
            "metadata": {"raw_code": data.get("code"), "source": source},
        }

    def submit_async_task(self, req_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"req_key": req_key, **payload}
        return self._post("CVSync2AsyncSubmitTask", "2022-08-31", body)

    def get_async_result(self, task_id: str, req_key: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"task_id": task_id}
        if req_key:
            payload["req_key"] = req_key
        return self._post("CVSync2AsyncGetResult", "2022-08-31", payload)

    def poll_async_result(
        self,
        task_id: str,
        req_key: str | None = None,
        interval: float = 3,
        max_wait: int = 300,
    ) -> JimengTaskResult:
        started = time.time()
        while time.time() - started < max_wait:
            data = self.get_async_result(task_id, req_key=req_key)
            text = json.dumps(data, ensure_ascii=False).lower()
            if data.get("status") == "error":
                return JimengTaskResult("error", data, round(time.time() - started, 2))
            if any(token in text for token in ("done", "success", "succeeded", "10000")):
                return JimengTaskResult("success", data, round(time.time() - started, 2))
            if any(token in text for token in ("failed", "error", "失败")):
                return JimengTaskResult("error", data, round(time.time() - started, 2))
            time.sleep(interval)
        return JimengTaskResult("timeout", {"task_id": task_id}, round(time.time() - started, 2))

    def async_capability_not_configured(self, capability: str) -> dict[str, Any]:
        return {
            "status": "error",
            "error": f"{capability} 需要先根据官方文档配置 req_key 和请求字段，再启用真实调用",
            "provider": "jimeng",
            "capability": capability,
        }

    def generate_image_46(self, prompt: str, width: int = 768, height: int = 1024, seed: int = -1) -> dict[str, Any]:
        return self.legacy_generate_image(prompt=prompt, width=width, height=height, seed=seed)

    def image_to_image_30(self, prompt: str, image_path: str) -> dict[str, Any]:
        return self.async_capability_not_configured("image_to_image_30")

    def inpaint_image(self, source_image: str, instruction: str) -> dict[str, Any]:
        return self.async_capability_not_configured("inpaint_image")

    def upscale_image(self, source_image: str, scale: int = 2) -> dict[str, Any]:
        return self.async_capability_not_configured("upscale_image")

    def generate_video_30_pro(self, prompt: str, source_image: str | None = None) -> dict[str, Any]:
        return self.async_capability_not_configured("generate_video_30_pro")

    def motion_mimic_20(self, source_image: str, motion_reference: str) -> dict[str, Any]:
        return self.async_capability_not_configured("motion_mimic_20")
