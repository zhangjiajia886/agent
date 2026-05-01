"""
工具执行器 —— 将 LLM tool_call 分派到 ComicAgent / ComfyUI / TTS 等真实后端。
每个执行函数: dict → dict，返回结构化结果（含 image_url / video_url / error）
"""
import asyncio
import glob as _glob
import os
import re
import tempfile
import uuid
import random
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from app.config import settings
from app.core.comfyui_client import comfyui_client
from app.core.jimeng_client import JimengProvider
from app.core.comic_agent.workflow_selector import (
    select_t2i, select_t2v, select_i2v, select_edit, select_upscale,
    load_workflow, inject_params,
)
from app.core.comic_chat_agent.sandbox import SandboxChecker


UPLOADS_DIR = Path(settings.UPLOAD_DIR).resolve() / "agent_outputs"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_MAX_OUTPUT_CHARS = 8_192
_TRUNCATION_HINT = "\n\n⚠️ 输出已截断，完整结果请写入文件查看。"
_BLOCKED_CMDS = ["rm -rf /", "mkfs", "dd if=/dev/zero", ":(){:|:&};:"]


def _jimeng_provider() -> JimengProvider:
    return JimengProvider(
        ak=settings.JIMENG_AK,
        sk=settings.JIMENG_SK,
        region=settings.JIMENG_REGION,
        host=settings.JIMENG_HOST,
        timeout=settings.JIMENG_TIMEOUT,
    )


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + _TRUNCATION_HINT


def _save_bytes(data: bytes, ext: str = "png") -> tuple[str, str]:
    """保存 bytes 到 uploads，返回 (相对URL, 文件系统绝对路径)"""
    fname = f"{uuid.uuid4().hex[:12]}.{ext}"
    fpath = UPLOADS_DIR / fname
    fpath.write_bytes(data)
    return f"/uploads/agent_outputs/{fname}", str(fpath)


def _resolve_media_path(path_or_url: str) -> str:
    """将 /uploads/... 相对 URL 或绝对路径解析为文件系统绝对路径"""
    if not path_or_url:
        return path_or_url
    # 已经是绝对路径且存在
    if os.path.isabs(path_or_url) and os.path.exists(path_or_url):
        return path_or_url
    # 相对 URL: /uploads/agent_outputs/xxx.png
    if path_or_url.startswith("/uploads/"):
        resolved = Path(settings.UPLOAD_DIR).resolve() / path_or_url[len("/uploads/"):]
        if resolved.exists():
            return str(resolved)
    # http://localhost:8000/uploads/...
    if "/uploads/" in path_or_url:
        suffix = path_or_url.split("/uploads/", 1)[1]
        resolved = Path(settings.UPLOAD_DIR).resolve() / suffix
        if resolved.exists():
            return str(resolved)
    return path_or_url


# ═══════════════════ ComfyUI 辅助 ═══════════════════

async def _check_comfyui() -> dict | None:
    """ComfyUI 前置健康检查，不可用时返回错误 dict，可用时返回 None"""
    if not settings.COMFYUI_ENABLED:
        return {"status": "error", "error": "ComfyUI 未启用，请在 .env 中设置 COMFYUI_ENABLED=true"}
    try:
        healthy = await comfyui_client.check_health()
        if not healthy:
            return {"status": "error", "error": "ComfyUI 服务不可达，请检查 AutoDL 实例是否开机"}
    except Exception as e:
        return {"status": "error", "error": f"ComfyUI 连接异常: {e}"}
    return None


async def _upload_image_to_comfyui(local_path: str) -> str:
    """读取本地图片文件并上传到 ComfyUI 服务器，返回 ComfyUI 端文件名"""
    local_path = _resolve_media_path(local_path)
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"图片文件不存在: {local_path}")
    image_bytes = Path(local_path).read_bytes()
    filename = os.path.basename(local_path)
    comfyui_filename = await comfyui_client.upload_image(image_bytes, filename)
    logger.info(f"[ToolExec] 已上传图片到 ComfyUI: {filename} -> {comfyui_filename}")
    return comfyui_filename


# ═══════════════════ generate_image ═══════════════════

async def execute_generate_image(params: dict) -> dict:
    """文生图：选工作流 → 注入提示词 → ComfyUI 执行 → 返回图片 URL"""
    prompt = params.get("prompt", "")
    style = params.get("style", "xianxia")
    width = params.get("width", 1024)
    height = params.get("height", 1024)
    seed = params.get("seed", -1)
    if seed == -1:
        seed = random.randint(0, 2**31)

    logger.info(f"[ToolExec] generate_image style={style} prompt={prompt[:50]}...")
    err = await _check_comfyui()
    if err:
        return err
    try:
        workflow_name = select_t2i(style, has_face=False)
        wf = load_workflow(workflow_name)
        wf = inject_params(
            wf,
            positive_prompt=prompt,
            negative_prompt="ugly, deformed, blurry, bad anatomy, watermark, text, low quality, nsfw",
            seed=seed,
            width=width,
            height=height,
        )
        image_bytes = await comfyui_client.run_workflow(wf)
        url, fpath = _save_bytes(image_bytes, "png")
        logger.info(f"[ToolExec] generate_image done → {url}")
        return {"status": "success", "image_url": url, "image_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] generate_image failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ generate_image_with_face ═══════════════════

async def execute_generate_image_with_face(params: dict) -> dict:
    """人脸保持生成：上传人脸 → InstantID 工作流 → 返回图片"""
    prompt = params.get("prompt", "")
    style = params.get("style", "xianxia")
    face_image = _resolve_media_path(params.get("face_image", ""))

    logger.info(f"[ToolExec] generate_image_with_face style={style}")
    err = await _check_comfyui()
    if err:
        return err
    try:
        comfyui_filename = await _upload_image_to_comfyui(face_image)
        workflow_name = select_t2i(style, has_face=True)
        wf = load_workflow(workflow_name)
        wf = inject_params(
            wf,
            positive_prompt=prompt,
            negative_prompt="ugly, deformed, blurry, bad anatomy, watermark, text, nsfw",
            seed=random.randint(0, 2**31),
            source_image=comfyui_filename,
        )
        image_bytes = await comfyui_client.run_workflow(wf)
        url, fpath = _save_bytes(image_bytes, "png")
        return {"status": "success", "image_url": url, "image_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] generate_image_with_face failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ edit_image ═══════════════════

async def execute_edit_image(params: dict) -> dict:
    """图像编辑：Qwen 编辑工作流"""
    source_image = _resolve_media_path(params.get("source_image", ""))
    instruction = params.get("instruction", "")

    logger.info(f"[ToolExec] edit_image instruction={instruction[:40]}...")
    err = await _check_comfyui()
    if err:
        return err
    try:
        comfyui_filename = await _upload_image_to_comfyui(source_image)
        wf = load_workflow("qwen_edit")
        wf = inject_params(
            wf,
            seed=random.randint(0, 2**31),
            instruction=instruction,
            edit_image=comfyui_filename,
        )
        image_bytes = await comfyui_client.run_workflow(wf)
        url, fpath = _save_bytes(image_bytes, "png")
        return {"status": "success", "image_url": url, "image_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] edit_image failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ image_to_video ═══════════════════

async def execute_image_to_video(params: dict) -> dict:
    """图生视频：Wan2.2 图生视频工作流"""
    source_image = _resolve_media_path(params.get("source_image", ""))
    motion_prompt = params.get("motion_prompt", "gentle camera movement, cinematic")

    logger.info(f"[ToolExec] image_to_video source={source_image} motion={motion_prompt[:40]}...")
    err = await _check_comfyui()
    if err:
        return err
    try:
        comfyui_filename = await _upload_image_to_comfyui(source_image)
        wf = load_workflow("wan_i2v")
        wf = inject_params(
            wf,
            positive_prompt=motion_prompt,
            negative_prompt="色调艳丽，过曝，静态，细节模糊不清，字幕，静止，最差质量",
            seed=random.randint(0, 2**31),
            source_image=comfyui_filename,
        )
        video_bytes = await comfyui_client.run_workflow_video(wf)
        url, fpath = _save_bytes(video_bytes, "mp4")
        return {"status": "success", "video_url": url, "video_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] image_to_video failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ text_to_video ═══════════════════

async def execute_text_to_video(params: dict) -> dict:
    """文生视频：Wan2.2 文生视频工作流"""
    prompt = params.get("prompt", "")
    style = params.get("style")  # wan_anime / wan_transparent / None

    logger.info(f"[ToolExec] text_to_video style={style} prompt={prompt[:50]}...")
    err = await _check_comfyui()
    if err:
        return err
    try:
        workflow_name = select_t2v(style)
        wf = load_workflow(workflow_name)
        wf = inject_params(
            wf,
            positive_prompt=prompt,
            negative_prompt="色调艳丽，过曝，静态，细节模糊不清，字幕，静止，最差质量",
            seed=random.randint(0, 2**31),
        )
        video_bytes = await comfyui_client.run_workflow_video(wf)
        url, fpath = _save_bytes(video_bytes, "mp4")
        return {"status": "success", "video_url": url, "video_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] text_to_video failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ upscale_image ═══════════════════

async def execute_upscale_image(params: dict) -> dict:
    """图像超分放大"""
    source_image = _resolve_media_path(params.get("source_image", ""))

    logger.info(f"[ToolExec] upscale_image source={source_image}")
    err = await _check_comfyui()
    if err:
        return err
    try:
        comfyui_filename = await _upload_image_to_comfyui(source_image)
        wf = load_workflow(select_upscale())
        wf = inject_params(wf, source_image=comfyui_filename, seed=random.randint(0, 2**31))
        image_bytes = await comfyui_client.run_workflow(wf)
        url, fpath = _save_bytes(image_bytes, "png")
        return {"status": "success", "image_url": url, "image_path": fpath}
    except Exception as e:
        logger.error(f"[ToolExec] upscale_image failed: {e}")
        return {"status": "error", "error": str(e)}


# ═══════════════════ text_to_speech ═══════════════════

async def execute_text_to_speech(params: dict) -> dict:
    """TTS 语音合成（调用 Fish Audio）"""
    text = params.get("text", "")
    voice_id = params.get("voice_id", settings.FISH_DEFAULT_VOICE)

    if not text.strip():
        return {"status": "error", "error": "缺少 text 参数，请提供要合成的文本"}

    logger.info(f"[ToolExec] text_to_speech text={text[:30]}...")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(
                f"{settings.FISH_API_URL}/v1/tts",
                headers={"Authorization": f"Bearer {settings.FISH_API_KEY}"},
                json={
                    "text": text,
                    "reference_id": voice_id,
                    "format": "mp3",
                },
            )
            if resp.status_code != 200:
                body = resp.text[:200] if resp.text else "(empty)"
                error_msg = f"Fish TTS HTTP {resp.status_code}: {body}"
                logger.error(f"[ToolExec] text_to_speech failed: {error_msg}")
                return {"status": "error", "error": error_msg}
            if len(resp.content) < 100:
                return {"status": "error", "error": f"TTS 返回数据太小({len(resp.content)}B)，可能是 API Key 无效或额度不足"}
            url, fpath = _save_bytes(resp.content, "mp3")
            return {"status": "success", "audio_url": url, "audio_path": fpath}
    except httpx.TimeoutException:
        logger.error("[ToolExec] text_to_speech timeout")
        return {"status": "error", "error": "TTS 请求超时(60s)，请检查 Fish Audio 服务是否可用"}
    except Exception as e:
        logger.error(f"[ToolExec] text_to_speech failed: {e}")
        return {"status": "error", "error": f"TTS 调用失败: {str(e)}"}


# ═══════════════════ merge_media / add_subtitle ═══════════════════

async def execute_merge_media(params: dict) -> dict:
    """媒体合成（暂返回占位）"""
    return {"status": "not_implemented", "error": "merge_media 尚未实现真实合成"}


async def execute_add_subtitle(params: dict) -> dict:
    """字幕叠加（暂返回占位）"""
    return {"status": "not_implemented", "error": "add_subtitle 尚未实现真实合成"}


# ═══════════════════ 通用工具 ═══════════════════

async def execute_bash(params: dict) -> dict:
    """执行 Shell 命令"""
    command = params.get("command", "")
    if not command:
        return {"error": "缺少 command 参数"}
    timeout = int(params.get("timeout", 30))
    cwd = params.get("working_dir") or None
    for pat in _BLOCKED_CMDS:
        if pat in command:
            return {"error": f"危险命令已拦截: {pat}", "code": -1}
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        return {
            "stdout": _truncate(stdout.decode(errors="replace")),
            "stderr": _truncate(stderr.decode(errors="replace")),
            "code": proc.returncode,
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": f"命令超时 ({timeout}s)", "code": -1}
    except Exception as e:
        return {"error": str(e), "code": -1}


async def execute_read_file(params: dict) -> dict:
    """读取文件内容"""
    path = params.get("path", "")
    if not path:
        return {"error": "缺少 path 参数"}
    offset = int(params.get("offset", 1))
    limit = params.get("limit")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, offset - 1)
        end = start + int(limit) if limit else len(lines)
        content = "".join(lines[start:end])
        return {"content": _truncate(content), "total_lines": len(lines)}
    except Exception as e:
        return {"error": str(e)}


async def execute_write_file(params: dict) -> dict:
    """写入文件内容"""
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return {"error": "缺少 path 参数"}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "bytes_written": len(content.encode("utf-8")), "path": path}
    except Exception as e:
        return {"error": str(e)}


async def execute_edit_file(params: dict) -> dict:
    """str_replace 精确编辑文件，支持 replace_all 全局替换"""
    path = params.get("path", "")
    old_string = params.get("old_string", "")
    new_string = params.get("new_string", "")
    replace_all = params.get("replace_all", False)
    if not path:
        return {"error": "缺少 path 参数"}
    if not old_string:
        return {"error": "缺少 old_string 参数"}
    try:
        # 解析相对路径
        resolved = _resolve_media_path(path)
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
        count = content.count(old_string)
        if count == 0:
            return {"error": f"old_string 在文件中未找到。文件前200字符: {content[:200]}"}
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced = count
        else:
            if count > 1:
                return {"error": f"old_string 在文件中出现 {count} 次，请设置 replace_all=true 或提供更多上下文"}
            new_content = content.replace(old_string, new_string, 1)
            replaced = 1
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"ok": True, "path": resolved, "replaced": replaced}
    except Exception as e:
        return {"error": str(e)}


async def execute_python_exec(params: dict) -> dict:
    """执行 Python 代码"""
    code = (params.get("code") or params.get("script") or "").strip()
    if not code:
        return {"error": "缺少 code 参数"}
    timeout = int(params.get("timeout", 60))
    # 使用后端目录作为 cwd，确保能访问项目文件
    exec_cwd = str(Path(__file__).resolve().parent.parent.parent)
    tmp_script = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir="/tmp", delete=False, encoding="utf-8"
    )
    try:
        tmp_script.write(code)
        tmp_script.close()
        # 使用 conda 环境的 python，回退到 python3
        python_bin = "/opt/homebrew/Caskroom/miniconda/base/envs/ttsapp/bin/python"
        if not os.path.exists(python_bin):
            python_bin = "python3"
        proc = await asyncio.create_subprocess_exec(
            python_bin, tmp_script.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=exec_cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        return {
            "stdout": _truncate(stdout.decode(errors="replace")),
            "stderr": _truncate(stderr.decode(errors="replace")),
            "code": proc.returncode,
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": f"Python 执行超时 ({timeout}s)", "code": -1}
    except Exception as e:
        return {"error": str(e), "code": -1}
    finally:
        try:
            os.unlink(tmp_script.name)
        except Exception:
            pass


async def execute_web_search(params: dict) -> dict:
    """网络搜索（DuckDuckGo）"""
    query = params.get("query", "")
    if not query:
        return {"error": "缺少 query 参数"}
    num = min(int(params.get("num_results", 5)), 10)
    try:
        from duckduckgo_search import DDGS
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(
            None, lambda: list(DDGS().text(query, max_results=num))
        )
        if raw:
            results = [{"title": r.get("title", ""), "snippet": r.get("body", ""),
                        "url": r.get("href", "")} for r in raw]
            return {"results": results, "query": query}
    except Exception as e:
        logger.warning(f"[ToolExec] web_search ddgs failed: {e}")
    # fallback: DuckDuckGo HTML
    try:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=15, verify=False) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            html_results = []
            for t, s in zip(titles[:num], snippets[:num]):
                t_clean = re.sub(r"<[^>]+>", "", t).strip()
                s_clean = re.sub(r"<[^>]+>", "", s).strip()
                if t_clean or s_clean:
                    html_results.append({"title": t_clean, "snippet": s_clean})
            if html_results:
                return {"results": html_results, "query": query}
    except Exception as e:
        return {"error": str(e), "query": query}
    return {"results": [{"text": "未找到相关结果"}], "query": query}


async def execute_web_fetch(params: dict) -> dict:
    """获取网页内容"""
    url = params.get("url", "")
    if not url:
        return {"error": "缺少 url 参数"}
    max_chars = int(params.get("max_chars", 8000))
    try:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=20, verify=False) as c:
            resp = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            ct = resp.headers.get("content-type", "")
            if "html" in ct:
                text = re.sub(r"<style[^>]*>.*?</style>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
            else:
                text = resp.text
            return {"url": url, "content": text[:max_chars], "status": resp.status_code}
    except Exception as e:
        return {"error": str(e), "url": url}


async def execute_grep_search(params: dict) -> dict:
    """搜索文件内容"""
    query = params.get("query", "")
    path = params.get("path", ".")
    if not query:
        return {"error": "缺少 query 参数"}
    includes = params.get("includes", [])
    cmd = f'grep -rn "{query}" "{path}"'
    if includes:
        for inc in includes:
            cmd += f' --include="{inc}"'
    cmd += " | head -50"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), 15)
        return {"matches": _truncate(stdout.decode(errors="replace"))}
    except Exception as e:
        return {"error": str(e)}


async def execute_find_files(params: dict) -> dict:
    """Glob 模式搜索文件"""
    pattern = params.get("pattern", "")
    if not pattern:
        return {"error": "缺少 pattern 参数"}
    base_dir = params.get("base_dir", ".")
    max_results = int(params.get("max_results", 50))
    try:
        full_pattern = os.path.join(base_dir, pattern)
        matches = _glob.glob(full_pattern, recursive=True)[:max_results]
        return {"matches": sorted(matches), "count": len(matches)}
    except Exception as e:
        return {"error": str(e)}


async def execute_list_dir(params: dict) -> dict:
    """列出目录内容"""
    path = params.get("path", ".")
    if not os.path.isdir(path):
        return {"error": f"路径不存在或不是目录: {path}"}
    try:
        items = []
        for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name)):
            try:
                item: dict[str, Any] = {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                }
                if entry.is_file():
                    item["size"] = entry.stat().st_size
                items.append(item)
            except PermissionError:
                pass
        return {"path": path, "items": items}
    except Exception as e:
        return {"error": str(e)}


async def execute_http_request(params: dict) -> dict:
    """发送 HTTP 请求"""
    url = params.get("url", "")
    if not url:
        return {"error": "缺少 url 参数"}
    method = params.get("method", "GET").upper()
    headers = params.get("headers", {})
    body = params.get("body")
    timeout = int(params.get("timeout", 30))
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=headers, content=body)
            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:50_000],
            }
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════ Jimeng 即梦工具 ═══════════════════

async def execute_jimeng_generate_image(params: dict) -> dict:
    if not settings.JIMENG_ENABLED:
        return {"status": "error", "error": "即梦未启用，请设置 JIMENG_ENABLED=true 并配置 JIMENG_AK/JIMENG_SK"}
    prompt = params.get("prompt", "")
    width = params.get("width") or settings.JIMENG_DEFAULT_WIDTH
    height = params.get("height") or settings.JIMENG_DEFAULT_HEIGHT
    seed = params.get("seed", -1)
    result = _jimeng_provider().generate_image_46(prompt=prompt, width=width, height=height, seed=seed)
    if result.get("status") != "success":
        return result
    image_url, image_path = _save_bytes(result["media_bytes"], result.get("media_ext", "png"))
    return {
        "status": "success",
        "provider": "jimeng",
        "capability": result.get("capability", "image_generation"),
        "model": result.get("model", settings.JIMENG_LEGACY_REQ_KEY),
        "image_url": image_url,
        "image_path": image_path,
        "file_urls": [image_url],
        "elapsed": result.get("elapsed"),
        "metadata": result.get("metadata", {}),
    }


async def execute_jimeng_reference_image(params: dict) -> dict:
    source_image = _resolve_media_path(params.get("source_image") or params.get("image") or "")
    prompt = params.get("prompt", "")
    return _jimeng_provider().image_to_image_30(prompt=prompt, image_path=source_image)


async def execute_jimeng_edit_image(params: dict) -> dict:
    source_image = _resolve_media_path(params.get("source_image") or "")
    instruction = params.get("instruction", "")
    return _jimeng_provider().inpaint_image(source_image=source_image, instruction=instruction)


async def execute_jimeng_upscale_image(params: dict) -> dict:
    source_image = _resolve_media_path(params.get("source_image") or "")
    scale = params.get("scale", 2)
    return _jimeng_provider().upscale_image(source_image=source_image, scale=scale)


async def execute_jimeng_generate_video(params: dict) -> dict:
    source_image = params.get("source_image")
    if source_image:
        source_image = _resolve_media_path(source_image)
    prompt = params.get("prompt") or params.get("motion_prompt") or ""
    return _jimeng_provider().generate_video_30_pro(prompt=prompt, source_image=source_image)


async def execute_jimeng_motion_mimic(params: dict) -> dict:
    source_image = _resolve_media_path(params.get("source_image") or "")
    motion_reference = _resolve_media_path(params.get("motion_reference") or params.get("reference_video") or "")
    return _jimeng_provider().motion_mimic_20(source_image=source_image, motion_reference=motion_reference)


# ═══════════════════ 执行器注册表 ═══════════════════

TOOL_EXECUTORS: dict[str, callable] = {
    # 漫剧专用工具
    "generate_image": execute_generate_image,
    "generate_image_with_face": execute_generate_image_with_face,
    "edit_image": execute_edit_image,
    "image_to_video": execute_image_to_video,
    "text_to_video": execute_text_to_video,
    "upscale_image": execute_upscale_image,
    "text_to_speech": execute_text_to_speech,
    "merge_media": execute_merge_media,
    "add_subtitle": execute_add_subtitle,
    "jimeng_generate_image": execute_jimeng_generate_image,
    "jimeng_reference_image": execute_jimeng_reference_image,
    "jimeng_edit_image": execute_jimeng_edit_image,
    "jimeng_upscale_image": execute_jimeng_upscale_image,
    "jimeng_generate_video": execute_jimeng_generate_video,
    "jimeng_motion_mimic": execute_jimeng_motion_mimic,
    # 通用工具
    "bash": execute_bash,
    "read_file": execute_read_file,
    "write_file": execute_write_file,
    "edit_file": execute_edit_file,
    "python_exec": execute_python_exec,
    "web_search": execute_web_search,
    "web_fetch": execute_web_fetch,
    "grep_search": execute_grep_search,
    "find_files": execute_find_files,
    "list_dir": execute_list_dir,
    "http_request": execute_http_request,
}


TOOL_ALIASES: dict[str, str] = {
    # ── 漫剧工具别名 ──
    "gen_image": "generate_image",
    "genimage": "generate_image",
    "create_image": "generate_image",
    "gen_image_face": "generate_image_with_face",
    "face_image": "generate_image_with_face",
    "img2video": "image_to_video",
    "img_to_video": "image_to_video",
    "i2v": "image_to_video",
    "t2v": "text_to_video",
    "gen_video": "text_to_video",
    "generate_video": "text_to_video",
    "txt2video": "text_to_video",
    "upscale": "upscale_image",
    "super_resolution": "upscale_image",
    "tts": "text_to_speech",
    "speech": "text_to_speech",
    "merge": "merge_media",
    "merge_video": "merge_media",
    "subtitle": "add_subtitle",
    "add_subtitles": "add_subtitle",
    "jimeng": "jimeng_generate_image",
    "jimeng_gen": "jimeng_generate_image",
    "jimeng_image": "jimeng_generate_image",
    "jimeng_i2i": "jimeng_reference_image",
    "jimeng_edit": "jimeng_edit_image",
    "jimeng_upscale": "jimeng_upscale_image",
    "jimeng_video": "jimeng_generate_video",
    "jimeng_motion": "jimeng_motion_mimic",
    # ── Python 执行 ──
    "execute_code": "python_exec",
    "run_code": "python_exec",
    "run_python": "python_exec",
    "python": "python_exec",
    "python_repl": "python_exec",
    # ── Shell ──
    "shell_exec": "bash",
    "run_shell": "bash",
    "shell": "bash",
    "execute_bash": "bash",
    "terminal": "bash",
    # ── 文件读取 ──
    "read_file_content": "read_file",
    "load_file": "read_file",
    "open_file": "read_file",
    "cat_file": "read_file",
    "view_file": "read_file",
    # ── 文件写入 ──
    "create_file": "write_file",
    "save_file": "write_file",
    "write_to_file": "write_file",
    "new_file": "write_file",
    # ── 文件编辑 ──
    "str_replace_editor": "edit_file",
    "replace_in_file": "edit_file",
    "modify_file": "edit_file",
    "update_file": "edit_file",
    # ── 网络搜索 ──
    "search_web": "web_search",
    "internet_search": "web_search",
    "google_search": "web_search",
    "bing_search": "web_search",
    "search": "web_search",
    # ── 网页抓取 ──
    "fetch_url": "web_fetch",
    "get_url": "web_fetch",
    "browse": "web_fetch",
    "open_url": "web_fetch",
    # ── 文件搜索 ──
    "search_files": "grep_search",
    "grep": "grep_search",
    "find_in_files": "grep_search",
    "find_file": "find_files",
    "glob": "find_files",
    "list_directory": "list_dir",
    "ls": "list_dir",
    # ── HTTP 请求 ──
    "make_request": "http_request",
    "api_call": "http_request",
    "curl": "http_request",
    "fetch": "http_request",
}


_sandbox = SandboxChecker()


async def execute_tool(tool_name: str, params: dict) -> dict:
    """统一入口：沙箱前置检查 + 别名解析 + 分派执行 + 统一 file_urls"""
    resolved = TOOL_ALIASES.get(tool_name, tool_name)
    # ── P7 沙箱前置检查 ──
    decision = _sandbox.check_tool(resolved, params)
    if not decision.allowed:
        logger.warning(f"[Sandbox] BLOCKED tool={resolved} check={decision.check_type} reason={decision.reason}")
        return {
            "status": "blocked",
            "error": decision.reason,
            "error_code": f"SANDBOX_{decision.check_type.upper()}_BLOCKED",
            "risk_level": decision.risk_level.name,
        }
    executor = TOOL_EXECUTORS.get(resolved)
    if not executor:
        return {"status": "error", "error": f"未知工具: {tool_name}"}
    result = await executor(params)
    # 统一 file_urls 字段
    urls = []
    for key in ("image_url", "video_url", "audio_url"):
        if result.get(key):
            urls.append(result[key])
    if urls:
        result["file_urls"] = urls
    return result
