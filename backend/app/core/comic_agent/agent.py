import random
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from app.core.comfyui_client import ComfyUIClient
from .intent_parser import parse_intent
from .story_planner import plan_storyboard
from .prompt_builder import build_all_prompts
from .workflow_selector import (
    select_workflow, select_t2v, select_upscale,
    load_workflow, inject_params,
)


@dataclass
class ComicRequest:
    description: str
    face_image: Optional[bytes] = None
    num_frames: int = 4
    include_video: bool = False
    lora_strength: float = 0.7
    seed: int = -1


@dataclass
class ComicResult:
    frames: list[bytes] = field(default_factory=list)
    video: Optional[bytes] = None
    storyboard: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    style: str = "xianxia"
    error: Optional[str] = None


class ComicAgent:
    def __init__(self, comfyui_client: ComfyUIClient, llm_client):
        self.comfyui = comfyui_client
        self.llm = llm_client

    async def generate(self, request: ComicRequest) -> ComicResult:
        result = ComicResult()
        seed = request.seed if request.seed != -1 else random.randint(0, 2**31)

        try:
            # Step 1: 解析意图
            logger.info(f"ComicAgent step1 parsing intent: {request.description[:30]}...")
            intent = await parse_intent(request.description, self.llm)
            style = intent["style"]
            story = intent["story"]
            mood = intent["mood"]
            num_frames = request.num_frames or intent.get("num_frames", 4)
            need_face = intent["need_face"] and request.face_image is not None
            result.style = style
            logger.info(f"  intent: style={style}, story={story}, need_face={need_face}")

            # Step 2: 规划分镜
            logger.info("ComicAgent step2 planning storyboard...")
            storyboard = await plan_storyboard(story, num_frames, style, mood, self.llm)
            result.storyboard = storyboard
            logger.info(f"  storyboard: {storyboard}")

            # Step 3: 生成提示词
            logger.info("ComicAgent step3 building prompts...")
            prompt_pairs = await build_all_prompts(storyboard, style, need_face, self.llm)
            result.prompts = [pos for pos, _ in prompt_pairs]
            logger.info(f"  prompts built: {len(prompt_pairs)} frames")

            # Step 4: 选择工作流
            workflow_name = select_workflow(style, need_face)
            logger.info(f"ComicAgent step4 workflow={workflow_name}")

            # Step 5: 上传人脸（如有）
            face_filename = None
            if need_face and request.face_image:
                face_filename = await self.comfyui.upload_image(
                    request.face_image, "face_ref.jpg"
                )
                logger.info(f"  face uploaded: {face_filename}")

            # Step 6: 逐格生成
            logger.info(f"ComicAgent step5 generating {num_frames} frames...")
            base_workflow = load_workflow(workflow_name)
            for i, (pos_prompt, neg_prompt) in enumerate(prompt_pairs):
                logger.info(f"  generating frame {i+1}/{num_frames}")
                workflow = inject_params(
                    base_workflow,
                    positive_prompt=pos_prompt,
                    negative_prompt=neg_prompt,
                    seed=seed + i,
                    lora_strength=request.lora_strength,
                    source_image=face_filename,
                )
                frame_bytes = await self.comfyui.run_workflow(workflow)
                result.frames.append(frame_bytes)
                logger.info(f"  frame {i+1} done, size={len(frame_bytes)} bytes")

            # Step 7: 可选视频化（仅对第一格）
            if request.include_video and result.frames:
                logger.info("ComicAgent step6 generating video (first frame)...")
                result.video = None

        except Exception as e:
            logger.error(f"ComicAgent failed: {e}", exc_info=True)
            result.error = str(e)

        return result

    async def edit_image(
        self,
        source_image: bytes,
        instruction: str,
        seed: int = -1,
    ) -> ComicResult:
        result = ComicResult()
        seed = seed if seed != -1 else random.randint(0, 2**31)
        try:
            logger.info(f"ComicAgent.edit_image instruction={instruction[:30]}...")
            filename = await self.comfyui.upload_image(source_image, "edit_source.jpg")
            workflow = load_workflow("qwen_edit")
            workflow = inject_params(
                workflow,
                seed=seed,
                instruction=instruction,
                edit_image=filename,
            )
            frame_bytes = await self.comfyui.run_workflow(workflow)
            result.frames = [frame_bytes]
            result.style = "edit"
        except Exception as e:
            logger.error(f"ComicAgent.edit_image failed: {e}", exc_info=True)
            result.error = str(e)
        return result

    async def animate_image(
        self,
        source_image: bytes,
        motion_prompt: str,
        seed: int = -1,
    ) -> ComicResult:
        result = ComicResult()
        seed = seed if seed != -1 else random.randint(0, 2**31)
        try:
            logger.info(f"ComicAgent.animate_image prompt={motion_prompt[:30]}...")
            filename = await self.comfyui.upload_image(source_image, "animate_source.jpg")
            workflow = load_workflow("wan_i2v")
            workflow = inject_params(
                workflow,
                positive_prompt=motion_prompt,
                negative_prompt="色调艳丽，过曝，静态，细节模糊不清，字幕，静止，整体发灰，最差质量",
                seed=seed,
                source_image=filename,
            )
            video_bytes = await self.comfyui.run_workflow_video(workflow)
            result.video = video_bytes
            result.style = "animate"
        except Exception as e:
            logger.error(f"ComicAgent.animate_image failed: {e}", exc_info=True)
            result.error = str(e)
        return result

    async def text_to_video(
        self,
        prompt: str,
        style: Optional[str] = None,
        seed: int = -1,
    ) -> ComicResult:
        result = ComicResult()
        seed = seed if seed != -1 else random.randint(0, 2**31)
        try:
            logger.info(f"ComicAgent.text_to_video prompt={prompt[:30]}... style={style}")
            workflow_name = select_t2v(style)
            workflow = load_workflow(workflow_name)
            workflow = inject_params(
                workflow,
                positive_prompt=prompt,
                negative_prompt="色调艳丽，过曝，静态，细节模糊不清，字幕，最差质量",
                seed=seed,
            )
            video_bytes = await self.comfyui.run_workflow_video(workflow)
            result.video = video_bytes
            result.style = f"t2v_{style or 'wan'}"
        except Exception as e:
            logger.error(f"ComicAgent.text_to_video failed: {e}", exc_info=True)
            result.error = str(e)
        return result

    async def upscale_image(
        self,
        source_image: bytes,
        seed: int = -1,
    ) -> ComicResult:
        result = ComicResult()
        seed = seed if seed != -1 else random.randint(0, 2**31)
        try:
            logger.info("ComicAgent.upscale_image")
            filename = await self.comfyui.upload_image(source_image, "upscale_source.jpg")
            workflow = load_workflow(select_upscale())
            workflow = inject_params(workflow, source_image=filename, seed=seed)
            frame_bytes = await self.comfyui.run_workflow(workflow)
            result.frames = [frame_bytes]
            result.style = "upscale"
        except Exception as e:
            logger.error(f"ComicAgent.upscale_image failed: {e}", exc_info=True)
            result.error = str(e)
        return result
