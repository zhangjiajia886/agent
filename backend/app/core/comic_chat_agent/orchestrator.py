"""
漫剧并行生成调度器 —— 多格漫剧并行生成，4 倍提速。

架构:
  Phase 1: 分镜规划（单次 LLM 调用 → JSON 数组）
  Phase 2: 并行图像生成（asyncio.gather + ComfyUI）
  Phase 3: 可选 TTS 旁白
  Phase 4: 汇总输出

来源: backend-myagent2/app/agent/orchestrator.py 简化版
"""
import json
import asyncio
from typing import AsyncIterator, Optional
from dataclasses import dataclass

from loguru import logger

from app.models.agent_config import ModelConfig
from .agent_runner import create_llm_client
from .tool_executor import execute_tool


# ═══════════════════ 常量 ═══════════════════

MAX_PARALLEL_FRAMES = 6      # 最大并行格数（受 ComfyUI GPU 限制）
FRAME_GEN_TIMEOUT = 120      # 单格生成超时（秒）


# ═══════════════════ 分镜规划 Prompt ═══════════════════

FRAME_PLANNING_PROMPT = """你是分镜规划师。根据用户的故事描述，生成 {num_frames} 格分镜。

输出 JSON 数组，每格包含:
- frame_number: 格号 (1-{num_frames})
- scene: 场景描述（中文，用于展示）
- prompt: 英文绘图提示词（含质量词 + 风格词，用于 AI 绘图）
- camera: 镜头类型（close-up/medium/wide/panoramic）

风格: {style}
风格关键词参考: {style_keywords}

要求:
1. 每格 prompt 必须是详细的英文描述，以 "masterpiece, best quality" 开头
2. prompt 中必须包含风格关键词
3. 每格场景有变化，讲述一个连贯的故事
4. camera 要有远近切换，增强叙事节奏

直接输出 JSON 数组，不要任何其他文字。"""

STYLE_KEYWORDS = {
    "xianxia": "xianxia style, ancient chinese, elegant hanfu, ethereal, jade accessories",
    "anime": "anime style, beautiful, sparkling eyes, vibrant colors, clean linework",
    "ink": "ink wash painting, sumi-e, monochrome, flowing brushstrokes",
    "blindbox": "blindbox style, chibi, 3d render, cute, pastel colors, kawaii",
    "realistic": "photorealistic, cinematic, 8k uhd, beautiful lighting",
    "flux": "ultra high quality, professional photography, sharp details",
}


# ═══════════════════ 数据结构 ═══════════════════

@dataclass
class FrameResult:
    """单格生成结果"""
    frame_idx: int
    success: bool
    image_url: str = ""
    error: str = ""
    scene: str = ""


# ═══════════════════ ComicOrchestrator ═══════════════════

class ComicOrchestrator:
    """漫剧多格并行调度器"""

    async def generate_comic_parallel(
        self,
        user_message: str,
        model_config: ModelConfig,
        num_frames: int = 4,
        style: str = "xianxia",
    ) -> AsyncIterator[dict]:
        """
        主入口: 分镜规划 → 并行生成 → 汇总。
        yield 的事件与前端 AgentEvent 完全兼容。
        """
        num_frames = min(num_frames, MAX_PARALLEL_FRAMES)
        llm, model_params = create_llm_client(model_config)
        model_name = model_config.model_id
        temperature = model_params.get("temperature", 0.7)
        max_tokens = model_params.get("max_tokens", 4096)

        yield {
            "type": "thinking",
            "content": (
                f"🎬 并行漫剧模式启动\n"
                f"🧠 模型: {model_name}\n"
                f"🎨 风格: {style} | 格数: {num_frames}\n"
                f"📝 故事: {user_message[:60]}{'...' if len(user_message) > 60 else ''}\n"
                f"⏳ Phase 1: 正在规划分镜..."
            ),
        }

        # ── Phase 1: 分镜规划 ──
        try:
            frames_plan = await self._plan_frames(
                llm, user_message, num_frames, style,
                temperature=temperature, max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"[Orchestrator] frame planning failed: {e}")
            yield {"type": "error", "content": f"分镜规划失败: {e}"}
            yield {"type": "done", "metadata": {"model": model_name, "error": str(e)}}
            return

        if not frames_plan or len(frames_plan) == 0:
            yield {"type": "error", "content": "分镜规划返回空结果"}
            yield {"type": "done", "metadata": {"model": model_name, "error": "empty plan"}}
            return

        # 展示分镜规划
        plan_text = "📋 分镜规划完成:\n"
        for fp in frames_plan:
            plan_text += f"  第{fp.get('frame_number', '?')}格: {fp.get('scene', '未知')} [{fp.get('camera', '?')}]\n"
        yield {"type": "thinking", "content": plan_text}
        yield {"type": "text", "content": plan_text}

        # ── Phase 2: 并行图像生成（流式推送） ──
        total = len(frames_plan)
        yield {
            "type": "thinking",
            "content": f"🖼️ Phase 2: 并行生成 {total} 格图片...",
        }

        # 为每格发送 tool_start 事件
        for i, frame in enumerate(frames_plan):
            yield {
                "type": "tool_start",
                "tool": "generate_image",
                "input": {
                    "frame": i + 1,
                    "scene": frame.get("scene", ""),
                    "prompt": frame.get("prompt", "")[:80],
                },
            }

        # 启动并行任务，通过 queue 流式收集结果
        queue: asyncio.Queue[FrameResult] = asyncio.Queue()

        async def _worker(idx: int, frame: dict):
            result = await self._generate_single_frame(idx, frame, style)
            await queue.put(result)

        tasks = [
            asyncio.create_task(_worker(i, frame))
            for i, frame in enumerate(frames_plan)
        ]

        # 逐个收取完成的帧，立即推送事件
        results: list[FrameResult] = []
        completed = 0
        while completed < total:
            r = await queue.get()
            completed += 1
            results.append(r)

            # 进度提示
            yield {
                "type": "thinking",
                "content": f"🖼️ 进度: {completed}/{total} 格完成",
            }

            # tool_done 事件
            if r.success:
                yield {
                    "type": "tool_done",
                    "tool": "generate_image",
                    "result": json.dumps({
                        "status": "success",
                        "image_url": r.image_url,
                        "frame": r.frame_idx + 1,
                        "scene": r.scene,
                    }, ensure_ascii=False),
                    "image_url": r.image_url,
                }
            else:
                yield {
                    "type": "tool_done",
                    "tool": "generate_image",
                    "result": json.dumps({
                        "status": "error",
                        "error": r.error,
                        "frame": r.frame_idx + 1,
                    }, ensure_ascii=False),
                }

        # 确保所有任务清理完毕
        await asyncio.gather(*tasks, return_exceptions=True)

        # ── Phase 3: 汇总输出 ──
        success_count = sum(1 for r in results if r.success)
        fail_count = total - success_count

        summary_lines = [f"🎉 {total} 格漫剧生成完毕！成功 {success_count} 格"]
        if fail_count > 0:
            summary_lines.append(f"⚠️ {fail_count} 格生成失败")
        for r in sorted(results, key=lambda x: x.frame_idx):
            if r.success:
                summary_lines.append(f"  第{r.frame_idx + 1}格: {r.scene} ✅")
            else:
                summary_lines.append(f"  第{r.frame_idx + 1}格: ❌ {r.error[:50]}")
        summary = "\n".join(summary_lines)
        yield {"type": "text", "content": summary}

        yield {
            "type": "done",
            "metadata": {
                "model": model_name,
                "mode": "parallel_comic",
                "total_frames": len(frames_plan),
                "success_frames": success_count,
                "failed_frames": fail_count,
                "style": style,
            },
        }

    # ── Phase 1: 分镜规划 ──

    async def _plan_frames(
        self,
        llm,
        user_message: str,
        num_frames: int,
        style: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> list[dict]:
        """用 LLM 生成分镜规划，返回 JSON 数组"""
        style_kw = STYLE_KEYWORDS.get(style, STYLE_KEYWORDS.get("xianxia", ""))
        system_prompt = FRAME_PLANNING_PROMPT.format(
            num_frames=num_frames,
            style=style,
            style_keywords=style_kw,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        logger.info(f"[Orchestrator] planning {num_frames} frames, style={style}")
        response = await llm.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        raw_text = response.content.strip()
        # 清理 markdown 代码块包裹
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_text = "\n".join(lines)

        try:
            frames = json.loads(raw_text)
            if not isinstance(frames, list):
                raise ValueError(f"Expected list, got {type(frames)}")
            logger.info(f"[Orchestrator] planned {len(frames)} frames")
            return frames[:num_frames]
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"[Orchestrator] JSON parse failed: {e}, raw={raw_text[:200]}")
            raise ValueError(f"分镜规划 JSON 解析失败: {e}") from e

    # ── Phase 2: 单格生成 ──

    async def _generate_single_frame(
        self,
        frame_idx: int,
        frame: dict,
        style: str,
    ) -> FrameResult:
        """生成单格图片（带超时保护）"""
        prompt = frame.get("prompt", "")
        scene = frame.get("scene", f"第{frame_idx + 1}格")

        if not prompt:
            return FrameResult(
                frame_idx=frame_idx, success=False,
                error="分镜缺少 prompt", scene=scene,
            )

        logger.info(f"[Orchestrator] generating frame {frame_idx + 1}: {scene}")

        try:
            result = await asyncio.wait_for(
                execute_tool("generate_image", {
                    "prompt": prompt,
                    "style": style,
                }),
                timeout=FRAME_GEN_TIMEOUT,
            )

            if result.get("status") == "success" and result.get("image_url"):
                return FrameResult(
                    frame_idx=frame_idx,
                    success=True,
                    image_url=result["image_url"],
                    scene=scene,
                )
            else:
                return FrameResult(
                    frame_idx=frame_idx,
                    success=False,
                    error=result.get("error", "未知错误"),
                    scene=scene,
                )
        except asyncio.TimeoutError:
            logger.error(f"[Orchestrator] frame {frame_idx + 1} timeout")
            return FrameResult(
                frame_idx=frame_idx, success=False,
                error=f"生成超时 ({FRAME_GEN_TIMEOUT}s)", scene=scene,
            )
        except Exception as e:
            logger.error(f"[Orchestrator] frame {frame_idx + 1} error: {e}")
            return FrameResult(
                frame_idx=frame_idx, success=False,
                error=str(e), scene=scene,
            )
