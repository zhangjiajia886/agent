"""
漫剧 Agent API 路由
- REST: 模型/工具/工作流 CRUD + 会话管理
- WebSocket: 流式 Agent 对话
- 种子数据: 首次启动自动插入 + AIPro 模型自动发现
"""
import asyncio
import uuid
import json
from datetime import datetime as _datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

import shutil as _shutil
from pathlib import Path as _Path

from app.config import settings
from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.agent_config import ModelConfig, ModelCategory, ToolRegistry, WorkflowTemplate, WorkflowCategory
from app.models.agent_chat import AgentConversation, AgentMessage, MessageRole, ConversationStatus
from app.models.agent_prompt import AgentPrompt
from app.models.agent_task import AgentArtifact, AgentEvent, AgentStep, AgentTask, ToolInvocation
from app.schemas.agent import (
    ModelConfigSchema, ModelConfigUpdate,
    ToolRegistrySchema, ToolRegistryUpdate,
    WorkflowTemplateSchema, WorkflowTemplateUpdate,
    ConversationCreate, ConversationSchema, ConversationListItem,
    AgentMessageSchema,
    AgentPromptSchema, AgentPromptUpdate,
)
from app.api.v1.auth import get_current_user
from app.core.comic_chat_agent.smart_agent import smart_agent_stream
from app.core.comic_chat_agent.agent_runner import agent_stream
from app.core.comic_chat_agent.orchestrator import ComicOrchestrator
from app.core.comic_agent.workflow_registry import scan_all as _scan_all_workflows

router = APIRouter()


# ═══════════════════ 种子数据 ═══════════════════

def _build_local_models() -> list[dict]:
    """从 settings 构建南格 + ComfyUI 本地模型种子"""
    models = []
    # 南格 主 LLM
    models.append({
        "name": f"主模型 ({settings.LLM_MODEL})",
        "category": "agent_brain", "provider": "southgrid",
        "base_url": settings.LLM_BASE_URL,
        "api_key": settings.LLM_API_KEY,
        "extra_auth": {"custcode": settings.LLM_CUSTCODE, "componentcode": settings.LLM_COMPONENTCODE},
        "model_id": settings.LLM_MODEL,
        "is_default": False, "is_enabled": True,
    })
    # 南格 L1 轻量 LLM
    models.append({
        "name": f"轻量模型 ({settings.L1_LLM_MODEL})",
        "category": "l1_llm", "provider": "southgrid",
        "base_url": settings.L1_LLM_BINDING_HOST,
        "api_key": settings.L1_LLM_BINDING_API_KEY,
        "extra_auth": {"custcode": settings.L1_LLM_CUSTCODE, "componentcode": settings.L1_LLM_COMPONENTCODE},
        "model_id": settings.L1_LLM_MODEL,
        "is_default": True, "is_enabled": True,
    })
    # 南格 多模态
    models.append({
        "name": f"多模态 ({settings.MMP_MODEL})",
        "category": "multimodal", "provider": "southgrid",
        "base_url": settings.MMP_BASE_URL,
        "api_key": settings.MMP_API_KEY,
        "extra_auth": {"custcode": settings.MMP_CUSTCODE, "componentcode": settings.MMP_COMPONENTCODE},
        "model_id": settings.MMP_MODEL,
        "is_default": True, "is_enabled": True,
    })
    # 南格 Embedding
    models.append({
        "name": f"Embedding ({settings.EMBEDDING_MODEL})",
        "category": "embedding", "provider": "southgrid",
        "base_url": settings.EMBEDDING_BASE_URL,
        "api_key": settings.EMBEDDING_API_KEY,
        "extra_auth": {"custcode": settings.EMBEDDING_CUSTCODE, "componentcode": settings.EMBEDDING_COMPONENTCODE},
        "model_id": settings.EMBEDDING_MODEL,
        "embedding_dim": settings.EMBEDDING_DIM,
        "is_default": True, "is_enabled": True,
    })
    # ComfyUI GPU
    if settings.COMFYUI_ENABLED:
        models.append({
            "name": "ComfyUI RTX5090 (AutoDL)",
            "category": "generation", "provider": "comfyui",
            "base_url": settings.COMFYUI_URL,
            "model_id": "comfyui-autodl-bjb1",
            "is_default": True, "is_enabled": True,
        })
    return models


async def _discover_aipro_models() -> list[dict]:
    """从 AIPro /v1/models 自动发现所有可用模型"""
    base_url = settings.AIPRO_BASE_URL
    api_key = settings.AIPRO_API_KEY
    if not base_url or not api_key:
        logger.warning("[Seed] AIPro 未配置, 跳过模型发现")
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        models = []
        default_model = settings.AIPRO_DEFAULT_MODEL
        for m in sorted(data, key=lambda x: x.get("id", "")):
            model_id = m.get("id", "")
            if not model_id:
                continue
            models.append({
                "name": f"[AIPro] {model_id}",
                "category": "agent_brain",
                "provider": "aipro",
                "base_url": base_url,
                "api_key": api_key,
                "model_id": model_id,
                "is_default": (model_id == default_model),
                "is_enabled": True,
            })
        logger.info(f"[Seed] AIPro 发现 {len(models)} 个模型")
        return models
    except Exception as e:
        logger.warning(f"[Seed] AIPro 模型发现失败: {e}")
        return []


SEED_TOOLS = [
    {"name": "generate_image", "display_name": "文生图", "description": "根据文字描述生成图片。输入 prompt（英文）、style、width、height、seed。", "executor_type": "comfyui", "sort_order": 1, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "style": {"type": "string"}, "width": {"type": "integer", "default": 1024}, "height": {"type": "integer", "default": 1024}, "seed": {"type": "integer", "default": -1}}, "required": ["prompt"]}},
    {"name": "generate_image_with_face", "display_name": "人脸保持生成", "description": "根据参考人脸和文字描述生成保持面部特征的图片。", "executor_type": "comfyui", "sort_order": 2, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "face_image": {"type": "string"}, "style": {"type": "string"}}, "required": ["prompt", "face_image"]}},
    {"name": "edit_image", "display_name": "图像编辑", "description": "对已有图片进行局部编辑。输入 source_image 路径和编辑指令。", "executor_type": "comfyui", "sort_order": 3, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string"}, "instruction": {"type": "string"}}, "required": ["source_image", "instruction"]}},
    {"name": "image_to_video", "display_name": "图生视频", "description": "将静态图片转为动态视频。输入 source_image 和运动描述。", "executor_type": "comfyui", "sort_order": 4, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string"}, "motion_prompt": {"type": "string"}}, "required": ["source_image"]}},
    {"name": "text_to_video", "display_name": "文生视频", "description": "根据文字描述直接生成视频（无需输入图片）。输入 prompt（英文运动描述）和可选 style（wan_anime=动漫风/wan_transparent=透明底）。生成约需2分钟。", "executor_type": "comfyui", "sort_order": 5, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "视频内容描述（英文）"}, "style": {"type": "string", "description": "风格: wan_anime/wan_transparent/默认真实风"}}, "required": ["prompt"]}},
    {"name": "text_to_speech", "display_name": "语音合成", "description": "将文字转为语音。输入 text 和可选的 voice_id。", "executor_type": "tts", "sort_order": 6, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "voice_id": {"type": "string"}}, "required": ["text"]}},
    {"name": "upscale_image", "display_name": "图像超分", "description": "对图片进行超分辨率放大。", "executor_type": "comfyui", "sort_order": 6, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string"}, "scale": {"type": "integer", "default": 2}}, "required": ["source_image"]}},
    {"name": "merge_media", "display_name": "媒体合成", "description": "将多个图片/视频/音频合成为最终视频。", "executor_type": "local", "sort_order": 7, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"frames": {"type": "array", "items": {"type": "string"}, "description": "图片或视频文件路径列表"}, "audio": {"type": "string", "description": "音频文件路径"}}, "required": ["frames"]}},
    {"name": "add_subtitle", "display_name": "字幕叠加", "description": "在视频上叠加字幕文字。", "executor_type": "local", "sort_order": 8, "is_enabled": False,
     "input_schema": {"type": "object", "properties": {"video": {"type": "string", "description": "视频文件路径"}, "subtitles": {"type": "array", "items": {"type": "object", "properties": {"text": {"type": "string"}, "start": {"type": "number"}, "end": {"type": "number"}}}, "description": "字幕列表"}}, "required": ["video", "subtitles"]}},
    {"name": "jimeng_generate_image", "display_name": "即梦文生图", "description": "使用即梦生成高画质图片。适合中文提示词、国风、仙侠、封面、关键帧。", "executor_type": "jimeng", "sort_order": 30, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "中文或英文图片描述"}, "width": {"type": "integer", "default": 768}, "height": {"type": "integer", "default": 1024}, "seed": {"type": "integer", "default": -1}}, "required": ["prompt"]}},
    {"name": "jimeng_reference_image", "display_name": "即梦图生图", "description": "使用即梦图生图/智能参考能力，适合参考图延展和角色一致性。", "executor_type": "jimeng", "sort_order": 31, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string", "description": "参考图片路径或 /uploads URL"}, "prompt": {"type": "string", "description": "生成描述"}}, "required": ["source_image", "prompt"]}},
    {"name": "jimeng_edit_image", "display_name": "即梦局部编辑", "description": "使用即梦 inpainting 能力对图片进行局部修改或修复。", "executor_type": "jimeng", "sort_order": 32, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string", "description": "待编辑图片路径或 /uploads URL"}, "instruction": {"type": "string", "description": "编辑指令"}}, "required": ["source_image", "instruction"]}},
    {"name": "jimeng_upscale_image", "display_name": "即梦智能超清", "description": "使用即梦智能超清提升图片清晰度。", "executor_type": "jimeng", "sort_order": 33, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string", "description": "图片路径或 /uploads URL"}, "scale": {"type": "integer", "default": 2}}, "required": ["source_image"]}},
    {"name": "jimeng_generate_video", "display_name": "即梦视频生成", "description": "使用即梦视频生成能力，适合文生视频、图生视频和关键镜头动态化。", "executor_type": "jimeng", "sort_order": 34, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string", "description": "视频描述"}, "source_image": {"type": "string", "description": "可选，图生视频源图片路径"}, "motion_prompt": {"type": "string", "description": "可选，运动描述"}}, "required": ["prompt"]}},
    {"name": "jimeng_motion_mimic", "display_name": "即梦动作模仿", "description": "使用即梦动作模仿2.0，让主体图模仿参考动作。", "executor_type": "jimeng", "sort_order": 35, "is_enabled": True,
     "input_schema": {"type": "object", "properties": {"source_image": {"type": "string", "description": "主体图片路径"}, "motion_reference": {"type": "string", "description": "动作参考视频或图片路径"}}, "required": ["source_image", "motion_reference"]}},
    # ── 通用工具 ──
    {"name": "bash", "display_name": "Shell 命令", "description": "执行 Shell 命令并返回输出。可指定 timeout 和 working_dir。", "executor_type": "local", "sort_order": 10,
     "input_schema": {"type": "object", "properties": {"command": {"type": "string", "description": "要执行的 Shell 命令"}, "timeout": {"type": "integer", "description": "超时秒数", "default": 30}, "working_dir": {"type": "string", "description": "工作目录"}}, "required": ["command"]}},
    {"name": "read_file", "display_name": "读取文件", "description": "读取文件内容。支持 offset（行号起始）和 limit（行数）参数读取大文件。", "executor_type": "local", "sort_order": 11,
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "文件路径"}, "offset": {"type": "integer", "description": "起始行号（1-indexed）", "default": 1}, "limit": {"type": "integer", "description": "读取行数"}}, "required": ["path"]}},
    {"name": "write_file", "display_name": "写入文件", "description": "将内容写入文件。自动创建父目录。", "executor_type": "local", "sort_order": 12,
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "文件路径"}, "content": {"type": "string", "description": "要写入的内容"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "display_name": "编辑文件", "description": "精确替换文件中的指定文本片段（str_replace）。old_string 必须在文件中唯一存在。", "executor_type": "local", "sort_order": 13,
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "文件路径"}, "old_string": {"type": "string", "description": "要替换的原始文本"}, "new_string": {"type": "string", "description": "替换后的新文本"}}, "required": ["path", "old_string", "new_string"]}},
    {"name": "python_exec", "display_name": "Python 执行", "description": "执行 Python 代码并返回 stdout/stderr。适合数据处理、计算、文件操作等。", "executor_type": "local", "sort_order": 14,
     "input_schema": {"type": "object", "properties": {"code": {"type": "string", "description": "要执行的 Python 代码"}, "timeout": {"type": "integer", "description": "超时秒数", "default": 60}}, "required": ["code"]}},
    {"name": "web_search", "display_name": "网络搜索", "description": "搜索网络获取最新信息。返回标题、摘要和链接。", "executor_type": "local", "sort_order": 15,
     "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}, "num_results": {"type": "integer", "description": "返回结果数量", "default": 5}}, "required": ["query"]}},
    {"name": "web_fetch", "display_name": "网页抓取", "description": "获取网页 URL 内容，自动提取纯文本。", "executor_type": "local", "sort_order": 16,
     "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "要获取的 URL"}, "max_chars": {"type": "integer", "description": "返回最大字符数", "default": 8000}}, "required": ["url"]}},
    {"name": "grep_search", "display_name": "内容搜索", "description": "在文件或目录中搜索匹配的文本模式（正则表达式）。", "executor_type": "local", "sort_order": 17,
     "input_schema": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索模式（正则表达式）"}, "path": {"type": "string", "description": "搜索路径（文件或目录）"}, "includes": {"type": "array", "items": {"type": "string"}, "description": "文件名 glob 过滤"}}, "required": ["query", "path"]}},
    {"name": "find_files", "display_name": "文件搜索", "description": "按 glob 模式搜索文件（支持 *, **, ?）。", "executor_type": "local", "sort_order": 18,
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string", "description": "glob 模式，如 '**/*.py'"}, "base_dir": {"type": "string", "description": "搜索起始目录", "default": "."}, "max_results": {"type": "integer", "description": "最大返回数量", "default": 50}}, "required": ["pattern"]}},
    {"name": "list_dir", "display_name": "目录列表", "description": "列出目录中的文件和子目录。", "executor_type": "local", "sort_order": 19,
     "input_schema": {"type": "object", "properties": {"path": {"type": "string", "description": "目录路径"}}, "required": ["path"]}},
    {"name": "http_request", "display_name": "HTTP 请求", "description": "发送 HTTP 请求（GET/POST/PUT/DELETE 等）。", "executor_type": "local", "sort_order": 20,
     "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "请求 URL"}, "method": {"type": "string", "description": "HTTP 方法", "default": "GET"}, "headers": {"type": "object", "description": "请求头"}, "body": {"type": "string", "description": "请求体"}, "timeout": {"type": "integer", "description": "超时秒数", "default": 30}}, "required": ["url"]}},
]


def _build_seed_prompts() -> list[dict]:
    """构建种子 Prompt 模板 — 覆盖所有节点"""
    return [
        {
            "node_name": "system",
            "display_name": "Agent System Prompt",
            "prompt_type": "system",
            "sort_order": 0,
            "content": (
                "你是「漫剧 Agent」，一个专业的 AI 漫画和视觉创作助手，同时具备通用编程和信息检索能力。\n\n"
                "## 你的能力\n"
                "### 创作工具\n"
                "- 根据用户描述生成各种风格的图片（仙侠/水墨/盲盒Q版/动漫/写实/Flux 等）\n"
                "- 将图片动态化为视频\n"
                "- 对已有图片进行编辑修改\n"
                "- 超分放大提升图片质量\n"
                "- 语音合成\n\n"
                "### 通用工具\n"
                "- **文件操作**: read_file / write_file / edit_file / list_dir / find_files / grep_search\n"
                "- **代码执行**: python_exec（执行 Python 代码）/ bash（Shell 命令）\n"
                "- **网络能力**: web_search（搜索引擎）/ web_fetch（抓取网页）/ http_request（HTTP 请求）\n\n"
                "## 工作流程（⚠️ 最高优先级，必须遵循）\n"
                "### 核心规则：说完计划立即动手，不要光说不做\n"
                "- **每次回复中必须同时包含工具调用**，不要只输出文字计划\n"
                "- 计划用 2-3 行简要列出即可，然后**立即调用第一个工具**\n"
                "- 禁止在一次回复中把所有文案/小说/脚本全部写完才开始调工具\n"
                "- 如果需要写长文案（如小说），使用 write_file 工具写入文件，而不是直接输出到聊天\n\n"
                "### 多步骤任务执行流程\n"
                "1. 简要列出步骤（2-3行），然后**立即调用工具开始第1步**\n"
                "2. 每步执行后，说明结果，继续下一步\n"
                "3. 工具返回的 `image_path` / `video_path` 是文件系统绝对路径，"
                "传给下一个工具的 `source_image` 参数时**必须使用绝对路径**\n"
                "4. 全部完成后简要汇总\n\n"
                "### 正确示例\n"
                "用户: 生成一张图然后转视频\n"
                "你: 分2步完成：1)生成图片 2)转视频。先生成图片：\n"
                "[立即调用 generate_image]\n\n"
                "### 错误示例（禁止）\n"
                "用户: 写一个小说然后生成视频\n"
                "你: [写了2000字小说但没有调用任何工具] ← 禁止！应该先用 write_file 保存小说，然后调工具\n\n"
                "## 工作原则\n"
                "1. 先理解用户意图，明确需求后再行动\n"
                "2. 创作前简要说明方案，然后**立即调用工具**\n"
                "3. 调用工具时 prompt 使用精确的英文描述，包含风格词和质量词\n"
                "4. 生成完成后询问用户是否满意\n"
                "5. 记住对话中之前的创作内容，支持引用和修改\n\n"
                "## 图像提示词规范\n"
                "- 必须使用英文\n"
                "- 开头加质量词: masterpiece, best quality, highly detailed\n"
                "- 根据 style 参数添加风格词:\n"
                "  - xianxia: xianxia style, ancient chinese, elegant hanfu, ethereal\n"
                "  - anime: anime style, beautiful, sparkling eyes, vibrant colors\n"
                "  - ink: ink wash painting, sumi-e, monochrome\n"
                "  - blindbox: chibi, 3d render, cute, pastel colors, kawaii\n"
                "  - realistic: photorealistic, cinematic, 8k uhd\n"
                "  - flux: ultra high quality, professional photography\n"
                "- style 参数可选值: xianxia / anime / ink / blindbox / realistic / flux\n\n"
                "## 重要\n"
                "- 如果用户只是聊天、问问题，直接友好回复，不要调用工具\n"
                "- 如果用户的请求模糊，先询问细节再动手\n"
                "- 每次只做用户要求的事，不要多余操作"
            ),
            "description": "Agent 主 system prompt，控制 LLM 的角色设定和行为准则。所有对话的起始指令。",
        },
        {
            "node_name": "intent_parser_system",
            "display_name": "意图解析 System",
            "prompt_type": "system",
            "sort_order": 10,
            "content": "你是一个专业的漫剧生成助手，负责理解用户的创作需求。",
            "description": "意图解析节点的 system prompt。在 HTTP 漫剧生成管线中使用。",
        },
        {
            "node_name": "intent_parser_user",
            "display_name": "意图解析 User 模板",
            "prompt_type": "user_template",
            "sort_order": 11,
            "content": (
                "分析以下用户描述，提取关键信息，以 JSON 格式返回：\n\n"
                "用户描述：{description}\n\n"
                "返回格式（纯 JSON，无其他文字）：\n"
                '{{\n'
                '  "style": "风格，必须是以下之一：xianxia（仙侠）/ blindbox（盲盒Q版）/ ink（水墨）/ anime（动漫）/ realistic（写实漫）",\n'
                '  "story": "核心故事情节，用中文简短描述（20字以内）",\n'
                '  "need_face": true或false（用户提到保留人脸/这张脸/人物特征时为true）,\n'
                '  "mood": "情感基调：epic（史诗）/ cute（可爱）/ dramatic（戏剧）/ peaceful（平和）",\n'
                '  "num_frames": 推断的格数，整数，1到8，默认4\n'
                '}}'
            ),
            "description": "意图解析 user 模板。可用变量: {description}",
        },
        {
            "node_name": "story_planner_system",
            "display_name": "分镜规划 System",
            "prompt_type": "system",
            "sort_order": 20,
            "content": "你是一个专业的漫剧分镜设计师，擅长将故事拆分为视觉化的分镜描述。",
            "description": "分镜规划节点的 system prompt。",
        },
        {
            "node_name": "story_planner_user",
            "display_name": "分镜规划 User 模板",
            "prompt_type": "user_template",
            "sort_order": 21,
            "content": (
                '为以下漫剧生成{num_frames}格分镜描述：\n'
                '- 风格：{style_zh}\n'
                '- 故事：{story}\n'
                '- 情感基调：{mood_zh}\n\n'
                '要求：\n'
                '1. 遵循\u201c起承转合\u201d结构（{num_frames}格均匀分配）\n'
                '2. 每格描述包含：景别（远景/中景/近景）、人物动作/状态、场景氛围\n'
                '3. 描述简洁，每格不超过30字\n'
                '4. 用中文描述\n\n'
                '以 JSON 数组返回（纯 JSON，无其他文字）：\n'
                '["格1描述", "格2描述", ...]'
            ),
            "description": '分镜规划 user 模板。可用变量: {num_frames}, {style_zh}, {story}, {mood_zh}',
        },
        {
            "node_name": "prompt_builder_system",
            "display_name": "提示词构建 System",
            "prompt_type": "system",
            "sort_order": 30,
            "content": "你是一个专业的 AI 图像生成提示词工程师，擅长将中文分镜描述转化为高质量的英文提示词。",
            "description": "提示词构建节点的 system prompt。",
        },
        {
            "node_name": "prompt_builder_user",
            "display_name": "提示词构建 User 模板",
            "prompt_type": "user_template",
            "sort_order": 31,
            "content": (
                "将以下中文分镜描述转化为英文图像生成提示词：\n\n"
                "分镜描述：{frame_desc}\n"
                "风格基调：{style_base}\n"
                "是否包含人脸：{has_face}\n\n"
                "要求：\n"
                "1. 用英文输出，不超过80个单词\n"
                "2. 包含：人物描述 + 动作/表情 + 场景 + 光线/氛围 + 质量词（masterpiece, best quality）\n"
                "3. 如果包含人脸，不要描述具体的人脸特征（由 InstantID 控制），只描述发型/服饰/动作\n"
                "4. 不要负向提示词，只输出正向提示词\n"
                "5. 直接输出提示词文本，不要有任何解释\n\n"
                "输出示例：\n"
                "xianxia style, 1girl from behind, standing at the foot of ethereal mountain, looking up at the peaks hidden in clouds, wide cinematic shot, golden hour lighting, masterpiece, best quality"
            ),
            "description": "提示词构建 user 模板。可用变量: {frame_desc}, {style_base}, {has_face}",
        },
    ]


async def seed_agent_data(db: AsyncSession):
    """检查表是否为空，为空则插入种子数据；模型表支持增量同步"""

    # ── Models: 增量同步（新模型自动添加，不删除已有） ──
    existing_models = {
        model.name: model
        for model in (await db.execute(select(ModelConfig))).scalars().all()
    }
    existing_model_ids = {model.model_id for model in existing_models.values()}
    all_models = _build_local_models() + await _discover_aipro_models()
    added = 0
    updated = 0
    for data in all_models:
        model = existing_models.get(data["name"])
        if model:
            for key, value in data.items():
                if getattr(model, key) != value:
                    setattr(model, key, value)
                    updated += 1
            existing_model_ids.add(data["model_id"])
        elif data["model_id"] not in existing_model_ids:
            db.add(ModelConfig(**data))
            existing_model_ids.add(data["model_id"])
            added += 1
    if added or updated:
        logger.info(f"[Seed] 模型同步: 新增 {added}, 更新 {updated}")

    # ── Tools（增量同步：新增不存在的工具，更新已有工具的描述和 schema）──
    existing_tools = {
        r[0]: r[1]
        for r in (await db.execute(select(ToolRegistry.name, ToolRegistry.id))).all()
    }
    tool_added = 0
    tool_updated = 0
    for data in SEED_TOOLS:
        if data["name"] not in existing_tools:
            db.add(ToolRegistry(**data))
            tool_added += 1
        else:
            tool_id = existing_tools[data["name"]]
            result = await db.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
            tool = result.scalar_one_or_none()
            if tool:
                tool.description = data["description"]
                tool.input_schema = data["input_schema"]
                tool.display_name = data["display_name"]
                tool.sort_order = data.get("sort_order", tool.sort_order)
                tool_updated += 1
    if tool_added or tool_updated:
        logger.info(f"[Seed] 工具同步: 新增 {tool_added}, 更新 {tool_updated}")

    # ── Workflows：扫描 workflows/ 目录自动 seed，增量补充 ──
    count = (await db.execute(select(sa_func.count(WorkflowTemplate.id)))).scalar() or 0
    scanned = _scan_all_workflows()
    if count < len(scanned):
        existing_names = set(
            r[0] for r in (await db.execute(select(WorkflowTemplate.name))).all()
        )
        wf_added = 0
        for data in scanned:
            fp = data.pop("_file_path", None)  # noqa
            if data["name"] not in existing_names:
                db.add(WorkflowTemplate(**data))
                wf_added += 1
        logger.info(f"[Seed] 补充插入 {wf_added} 个工作流模板（共 {len(scanned)}）")

    # ── Prompts：种子 prompt 模板（增量补充） ──
    existing_prompt_nodes = set(
        r[0] for r in (await db.execute(select(AgentPrompt.node_name))).all()
    )
    seed_prompts = _build_seed_prompts()
    p_added = 0
    p_updated = 0
    for data in seed_prompts:
        if data["node_name"] not in existing_prompt_nodes:
            db.add(AgentPrompt(**data))
            existing_prompt_nodes.add(data["node_name"])
            p_added += 1
        else:
            result = await db.execute(
                select(AgentPrompt).where(AgentPrompt.node_name == data["node_name"])
            )
            prompt = result.scalar_one_or_none()
            if prompt and prompt.content != data["content"]:
                prompt.content = data["content"]
                p_updated += 1
    if p_added or p_updated:
        logger.info(f"[Seed] Prompt 同步: 新增 {p_added}, 更新 {p_updated}")

    await db.commit()


# ═══════════════════ 模型 CRUD ═══════════════════

@router.get("/models", response_model=List[ModelConfigSchema])
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.id))
    return result.scalars().all()


@router.put("/models/{model_id}", response_model=ModelConfigSchema)
async def update_model(
    model_id: int,
    data: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    if data.is_enabled is not None:
        model.is_enabled = data.is_enabled
    if data.is_default is not None:
        model.is_default = data.is_default
    if data.model_params is not None:
        model.model_params = data.model_params
    if data.base_url is not None:
        model.base_url = data.base_url
    if data.api_key is not None:
        model.api_key = data.api_key
    if data.model_id is not None:
        model.model_id = data.model_id
    await db.commit()
    await db.refresh(model)
    return model


# ═══════════════════ 工具 CRUD ═══════════════════

@router.get("/tools", response_model=List[ToolRegistrySchema])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ToolRegistry).order_by(ToolRegistry.sort_order))
    return result.scalars().all()


@router.put("/tools/{tool_id}", response_model=ToolRegistrySchema)
async def update_tool(
    tool_id: int,
    data: ToolRegistryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ToolRegistry).where(ToolRegistry.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    if data.is_enabled is not None:
        tool.is_enabled = data.is_enabled
    if data.sort_order is not None:
        tool.sort_order = data.sort_order
    await db.commit()
    await db.refresh(tool)
    return tool


# ═══════════════════ 工作流 CRUD ═══════════════════

@router.get("/workflows", response_model=List[WorkflowTemplateSchema])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(WorkflowTemplate).order_by(WorkflowTemplate.id))
    return result.scalars().all()


@router.put("/workflows/{wf_id}", response_model=WorkflowTemplateSchema)
async def update_workflow(
    wf_id: int,
    data: WorkflowTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(WorkflowTemplate).where(WorkflowTemplate.id == wf_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    if data.is_enabled is not None:
        wf.is_enabled = data.is_enabled
    await db.commit()
    await db.refresh(wf)
    return wf


# ═══════════════════ Prompt 管理 CRUD ═══════════════════

@router.get("/prompts", response_model=List[AgentPromptSchema])
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentPrompt).order_by(AgentPrompt.sort_order))
    return result.scalars().all()


@router.put("/prompts/{prompt_id}", response_model=AgentPromptSchema)
async def update_prompt(
    prompt_id: int,
    data: AgentPromptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(AgentPrompt).where(AgentPrompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 不存在")
    if data.content is not None:
        prompt.content = data.content
    if data.is_enabled is not None:
        prompt.is_enabled = data.is_enabled
    if data.display_name is not None:
        prompt.display_name = data.display_name
    if data.description is not None:
        prompt.description = data.description
    await db.commit()
    await db.refresh(prompt)
    return prompt


# ═══════════════════ 会话 CRUD ═══════════════════

def _dt(value):
    return value.isoformat() if value else None


def _task_payload(task: AgentTask) -> dict:
    return {
        "id": task.id,
        "task_uid": task.task_uid,
        "conversation_id": task.conversation_id,
        "user_id": task.user_id,
        "user_goal": task.user_goal,
        "task_type": task.task_type,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "current_step_uid": task.current_step_uid,
        "model_id": task.model_id,
        "auto_mode": task.auto_mode,
        "final_report": task.final_report,
        "error": task.error,
        "metadata": task.metadata_json,
        "created_at": _dt(task.created_at),
        "updated_at": _dt(task.updated_at),
        "finished_at": _dt(task.finished_at),
    }


def _step_payload(step: AgentStep) -> dict:
    return {
        "id": step.id,
        "step_uid": step.step_uid,
        "task_uid": step.task_uid,
        "parent_step_uid": step.parent_step_uid,
        "title": step.title,
        "description": step.description,
        "step_type": step.step_type,
        "tool_name": step.tool_name,
        "status": step.status.value if hasattr(step.status, "value") else step.status,
        "depends_on": step.depends_on,
        "inputs": step.inputs,
        "outputs": step.outputs,
        "error": step.error,
        "retry_count": step.retry_count,
        "max_retries": step.max_retries,
        "sort_order": step.sort_order,
        "created_at": _dt(step.created_at),
        "updated_at": _dt(step.updated_at),
        "started_at": _dt(step.started_at),
        "finished_at": _dt(step.finished_at),
    }


def _artifact_payload(artifact: AgentArtifact) -> dict:
    return {
        "id": artifact.id,
        "artifact_uid": artifact.artifact_uid,
        "task_uid": artifact.task_uid,
        "step_uid": artifact.step_uid,
        "artifact_type": artifact.artifact_type,
        "title": artifact.title,
        "url": artifact.url,
        "file_path": artifact.file_path,
        "mime_type": artifact.mime_type,
        "size_bytes": artifact.size_bytes,
        "verified": artifact.verified,
        "metadata": artifact.metadata_json,
        "created_at": _dt(artifact.created_at),
    }


def _event_payload(event: AgentEvent) -> dict:
    return {
        "id": event.id,
        "event_uid": event.event_uid,
        "task_uid": event.task_uid,
        "step_uid": event.step_uid,
        "event_type": event.event_type,
        "payload": event.payload,
        "created_at": _dt(event.created_at),
    }


def _tool_invocation_payload(invocation: ToolInvocation) -> dict:
    return {
        "id": invocation.id,
        "invocation_uid": invocation.invocation_uid,
        "task_uid": invocation.task_uid,
        "step_uid": invocation.step_uid,
        "tool_call_id": invocation.tool_call_id,
        "tool_name": invocation.tool_name,
        "input": invocation.input,
        "output": invocation.output,
        "status": invocation.status,
        "error": invocation.error,
        "started_at": _dt(invocation.started_at),
        "finished_at": _dt(invocation.finished_at),
        "created_at": _dt(invocation.created_at),
    }


async def _get_owned_task(task_uid: str, db: AsyncSession, current_user: User) -> AgentTask:
    result = await db.execute(
        select(AgentTask).where(
            AgentTask.task_uid == task_uid,
            AgentTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get("/conversations", response_model=List[ConversationListItem])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentConversation)
        .where(
            AgentConversation.user_id == current_user.id,
            AgentConversation.status != ConversationStatus.deleted,
        )
        .order_by(AgentConversation.updated_at.desc())
        .offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.post("/conversations", response_model=ConversationSchema)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = AgentConversation(
        session_id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=data.title or "新漫剧对话",
    )
    db.add(conv)
    await db.commit()
    result = await db.execute(
        select(AgentConversation)
        .options(selectinload(AgentConversation.messages))
        .where(AgentConversation.id == conv.id)
    )
    return result.scalar_one()


@router.get("/conversations/{conv_id}", response_model=ConversationSchema)
async def get_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentConversation)
        .options(selectinload(AgentConversation.messages))
        .where(
            AgentConversation.id == conv_id,
            AgentConversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentConversation).where(
            AgentConversation.id == conv_id,
            AgentConversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    conv.status = ConversationStatus.deleted
    await db.commit()
    return {"message": "会话已删除"}


# ═══════════════════ Agent 任务查询 ═══════════════════

@router.get("/tasks/{task_uid}")
async def get_agent_task(
    task_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await _get_owned_task(task_uid, db, current_user)
    steps_result = await db.execute(
        select(AgentStep)
        .where(AgentStep.task_uid == task_uid)
        .order_by(AgentStep.sort_order, AgentStep.id)
    )
    artifacts_result = await db.execute(
        select(AgentArtifact)
        .where(AgentArtifact.task_uid == task_uid)
        .order_by(AgentArtifact.id)
    )
    invocations_result = await db.execute(
        select(ToolInvocation)
        .where(ToolInvocation.task_uid == task_uid)
        .order_by(ToolInvocation.id)
    )
    return {
        "task": _task_payload(task),
        "steps": [_step_payload(row) for row in steps_result.scalars().all()],
        "artifacts": [_artifact_payload(row) for row in artifacts_result.scalars().all()],
        "tool_invocations": [_tool_invocation_payload(row) for row in invocations_result.scalars().all()],
    }


@router.get("/tasks/{task_uid}/events")
async def list_agent_task_events(
    task_uid: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_task(task_uid, db, current_user)
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.task_uid == task_uid)
        .order_by(AgentEvent.id)
        .offset(skip)
        .limit(limit)
    )
    return [_event_payload(row) for row in result.scalars().all()]


@router.get("/tasks/{task_uid}/artifacts")
async def list_agent_task_artifacts(
    task_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_task(task_uid, db, current_user)
    result = await db.execute(
        select(AgentArtifact)
        .where(AgentArtifact.task_uid == task_uid)
        .order_by(AgentArtifact.id)
    )
    return [_artifact_payload(row) for row in result.scalars().all()]


@router.post("/tasks/{task_uid}/cancel")
async def cancel_agent_task(
    task_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消正在执行的任务"""
    task = await _get_owned_task(task_uid, db, current_user)
    if task.status in ("completed", "failed", "canceled"):
        raise HTTPException(400, f"任务已处于终态: {task.status}")
    task.status = "canceled"
    task.finished_at = _datetime.utcnow()
    # 将所有 pending/running step 置为 canceled
    steps_result = await db.execute(
        select(AgentStep).where(
            AgentStep.task_uid == task_uid,
            AgentStep.status.in_(["pending", "running", "ready", "awaiting_approval"]),
        )
    )
    for step in steps_result.scalars().all():
        step.status = "canceled"
    await db.commit()
    return {"task_uid": task_uid, "status": "canceled"}


@router.get("/tasks/{task_uid}/trace")
async def get_task_trace(
    task_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取任务的工具调用详情时间线"""
    await _get_owned_task(task_uid, db, current_user)
    invocations_result = await db.execute(
        select(ToolInvocation)
        .where(ToolInvocation.task_uid == task_uid)
        .order_by(ToolInvocation.id)
    )
    events_result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.task_uid == task_uid)
        .order_by(AgentEvent.id)
    )
    return {
        "task_uid": task_uid,
        "tool_invocations": [_tool_invocation_payload(row) for row in invocations_result.scalars().all()],
        "events": [_event_payload(row) for row in events_result.scalars().all()],
    }


@router.post("/tasks/{task_uid}/steps/{step_uid}/retry")
async def retry_task_step(
    task_uid: str,
    step_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重试指定步骤（将 failed 步骤重置为 pending）"""
    await _get_owned_task(task_uid, db, current_user)
    step_result = await db.execute(
        select(AgentStep).where(
            AgentStep.task_uid == task_uid,
            AgentStep.step_uid == step_uid,
        )
    )
    step = step_result.scalar_one_or_none()
    if not step:
        raise HTTPException(404, "步骤不存在")
    if step.status not in ("failed", "blocked"):
        raise HTTPException(400, f"步骤状态 {step.status} 不可重试，仅 failed/blocked 可重试")
    step.status = "pending"
    step.error = None
    await db.commit()
    return {"task_uid": task_uid, "step_uid": step_uid, "status": "pending"}


@router.get("/tools/health")
async def check_tools_health(
    current_user: User = Depends(get_current_user),
):
    """检查所有已注册工具的健康状态"""
    from app.core.comic_chat_agent.tool_capability import TOOL_CAPABILITIES
    health: list[dict] = []
    for name, cap in TOOL_CAPABILITIES.items():
        health.append({
            "tool_name": name,
            "risk_level": cap.risk_level,
            "cost_level": cap.cost_level,
            "needs_approval": cap.needs_approval,
            "fallback_tools": list(cap.fallback_tools),
            "status": "available",
        })
    return {"tools": health, "total": len(health)}


@router.get("/tools/stats")
async def get_tool_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取工具调用统计"""
    result = await db.execute(
        select(
            ToolInvocation.tool_name,
            sa_func.count().label("total"),
            sa_func.count().filter(ToolInvocation.status == "succeeded").label("succeeded"),
            sa_func.count().filter(ToolInvocation.status == "failed").label("failed"),
        )
        .join(AgentTask, AgentTask.task_uid == ToolInvocation.task_uid)
        .where(AgentTask.user_id == current_user.id)
        .group_by(ToolInvocation.tool_name)
    )
    stats = []
    for row in result.all():
        total = row.total or 0
        succeeded = row.succeeded or 0
        stats.append({
            "tool_name": row.tool_name,
            "total_calls": total,
            "succeeded": succeeded,
            "failed": row.failed or 0,
            "success_rate": round(succeeded / total, 2) if total > 0 else 0,
        })
    return {"stats": stats}


@router.get("/conversations/{conversation_id}/tasks")
async def list_conversation_agent_tasks(
    conversation_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv_result = await db.execute(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.user_id == current_user.id,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")
    result = await db.execute(
        select(AgentTask)
        .where(
            AgentTask.conversation_id == conversation_id,
            AgentTask.user_id == current_user.id,
        )
        .order_by(AgentTask.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return [_task_payload(row) for row in result.scalars().all()]


# ═══════════════════ 图片上传 ═══════════════════

_UPLOAD_DIR = _Path(settings.UPLOAD_DIR).resolve() / "agent_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传图片附件，返回文件路径和访问 URL"""
    ext = _Path(file.filename or "img.png").suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 {_ALLOWED_EXTS}")
    if file.size and file.size > 20 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 20MB")

    filename = f"{uuid.uuid4().hex[:12]}{ext}"
    dest = _UPLOAD_DIR / filename
    with open(dest, "wb") as f:
        _shutil.copyfileobj(file.file, f)

    file_url = f"/api/v1/files/agent_uploads/{filename}"
    return {"file_path": str(dest), "file_url": file_url, "filename": filename}


# ═══════════════════ WebSocket Agent 对话 ═══════════════════

@router.websocket("/ws/chat")
async def websocket_agent_chat(
    websocket: WebSocket,
    conversation_id: int = 0,
    token: str = "",
):
    """
    WebSocket 流式 Agent 对话
    URL: /api/v1/comic-agent/ws/chat?conversation_id=xxx&token=yyy
    """
    from app.core.security import verify_token
    await websocket.accept()

    # 鉴权
    user_id = verify_token(token)
    if not user_id:
        await websocket.send_json({"type": "error", "content": "认证失败"})
        await websocket.close(code=1008)
        return

    user_id = int(user_id)

    # 获取或创建会话
    async with AsyncSessionLocal() as db:
        if conversation_id > 0:
            result = await db.execute(
                select(AgentConversation).where(
                    AgentConversation.id == conversation_id,
                    AgentConversation.user_id == user_id,
                )
            )
            conv = result.scalar_one_or_none()
            if not conv:
                await websocket.send_json({"type": "error", "content": "会话不存在"})
                await websocket.close(code=1008)
                return
        else:
            conv = AgentConversation(
                session_id=str(uuid.uuid4()),
                user_id=user_id,
                title="新漫剧对话",
            )
            db.add(conv)
            await db.commit()
            await db.refresh(conv)
            await websocket.send_json({
                "type": "conversation_created",
                "conversation_id": conv.id,
                "session_id": conv.session_id,
            })

        conv_id = conv.id

    logger.info(f"[AgentWS] connected: user={user_id}, conv={conv_id}")

    try:
        while True:
            data = await websocket.receive_json()
            # 审批消息不含 message 字段，跳过（审批在 agent 循环内部处理）
            if data.get("action") in ("approve", "reject"):
                continue
            message = data.get("message", "").strip()
            if not message:
                continue

            style = data.get("style", "auto")
            frames = data.get("frames", 0)
            model_id = data.get("model", "")
            auto_mode = data.get("auto_mode", False)
            image_paths = data.get("image_paths", [])

            # 如果有图片附件，将路径信息追加到消息中
            if image_paths:
                paths_text = "\n".join(f"[用户附件图片] {p}" for p in image_paths)
                message = f"{message}\n\n{paths_text}"

            # 保存用户消息
            async with AsyncSessionLocal() as db:
                user_msg = AgentMessage(
                    conversation_id=conv_id,
                    role=MessageRole.user,
                    content=message,
                )
                db.add(user_msg)
                await db.commit()

            # ── 决定使用 Agent 模式还是 Smart 模式 ──
            all_events = []

            if model_id:
                # Agent 模式：用户选了模型 → LLM ReAct 循环
                async with AsyncSessionLocal() as db:
                    # 查模型配置
                    model_config = None
                    result = await db.execute(
                        select(ModelConfig).where(
                            ModelConfig.model_id == model_id,
                            ModelConfig.is_enabled == True,
                        )
                    )
                    model_config = result.scalar_one_or_none()

                    if not model_config:
                        await websocket.send_json({
                            "type": "error",
                            "content": f"模型 {model_id} 未找到或未启用",
                        })
                        await websocket.send_json({"type": "done"})
                        continue

                    # 加载对话历史
                    history_result = await db.execute(
                        select(AgentMessage)
                        .where(AgentMessage.conversation_id == conv_id)
                        .order_by(AgentMessage.id)
                    )
                    history = [
                        {"role": m.role.value, "content": m.content or ""}
                        for m in history_result.scalars()
                        if m.role in (MessageRole.user, MessageRole.assistant)
                    ][:-1]  # 排除刚刚保存的 user 消息（会在 build_messages 中加）

                    # 判断是否走并行漫剧模式
                    use_parallel = (
                        frames > 1
                        and style != "auto"
                    )

                    agent_done_sent = False
                    if use_parallel:
                        # 并行漫剧模式
                        orch = ComicOrchestrator()
                        async for event in orch.generate_comic_parallel(
                            user_message=message,
                            model_config=model_config,
                            num_frames=frames,
                            style=style,
                        ):
                            await websocket.send_json(event)
                            if event.get("type") == "done":
                                agent_done_sent = True
                            else:
                                all_events.append(event)
                    else:
                        # 标准 ReAct Agent 循环（带工具确认机制）
                        approval_queue: asyncio.Queue = asyncio.Queue()
                        event_queue: asyncio.Queue = asyncio.Queue()
                        agent_finished = asyncio.Event()

                        async def _run_agent():
                            try:
                                async for event in agent_stream(
                                    user_message=message,
                                    model_config=model_config,
                                    db=db,
                                    conversation_history=history,
                                    approval_queue=approval_queue,
                                    auto_mode=auto_mode,
                                    conversation_id=conv_id,
                                    user_id=user_id,
                                ):
                                    await event_queue.put(event)
                            except Exception as exc:
                                await event_queue.put({"type": "error", "content": str(exc)})
                            finally:
                                agent_finished.set()

                        agent_task = asyncio.create_task(_run_agent())

                        # 分发事件 + 监听审批
                        while not agent_finished.is_set() or not event_queue.empty():
                            # 优先发送已有事件
                            while not event_queue.empty():
                                event = event_queue.get_nowait()
                                await websocket.send_json(event)
                                if event.get("type") == "done":
                                    agent_done_sent = True
                                elif event.get("type") == "tool_confirm":
                                    # 等待用户审批
                                    try:
                                        approval_data = await asyncio.wait_for(
                                            websocket.receive_json(), timeout=300
                                        )
                                        action = approval_data.get("action", "")
                                        if action in ("approve", "reject"):
                                            await approval_queue.put(approval_data)
                                        else:
                                            await approval_queue.put({"action": "approve"})
                                    except asyncio.TimeoutError:
                                        await approval_queue.put({"action": "reject", "reason": "超时"})
                                    except Exception:
                                        await approval_queue.put({"action": "reject", "reason": "连接异常"})
                                else:
                                    all_events.append(event)

                            if not agent_finished.is_set():
                                await asyncio.sleep(0.05)

                        # 确保 agent task 完成
                        await agent_task
            else:
                agent_done_sent = False
                # Smart 模式：无模型 → 关键词分发
                async for event in smart_agent_stream(message, style, frames):
                    await websocket.send_json(event)
                    all_events.append(event)

            # 保存 assistant 消息（合并文字 + delta 事件）
            text_parts = []
            delta_parts = []
            for e in all_events:
                if e.get("type") == "text" and e.get("content"):
                    text_parts.append(e["content"])
                elif e.get("type") == "delta" and e.get("content"):
                    delta_parts.append(e["content"])
            full_text = "\n\n".join(text_parts) if text_parts else "".join(delta_parts)

            tool_calls = [
                {"tool": e["tool"], "input": e.get("input")}
                for e in all_events if e.get("type") == "tool_start"
            ]
            tool_results = [
                {"tool": e["tool"], "result": e.get("result")}
                for e in all_events if e.get("type") == "tool_done"
            ]

            async with AsyncSessionLocal() as db:
                ai_msg = AgentMessage(
                    conversation_id=conv_id,
                    role=MessageRole.assistant,
                    content=full_text,
                    tool_calls=tool_calls if tool_calls else None,
                    tool_result=tool_results if tool_results else None,
                )
                db.add(ai_msg)

                # 更新会话标题（第一条消息时）
                conv_result = await db.execute(
                    select(AgentConversation).where(AgentConversation.id == conv_id)
                )
                conv_obj = conv_result.scalar_one_or_none()
                if conv_obj and conv_obj.title == "新漫剧对话":
                    conv_obj.title = message[:30] + ("..." if len(message) > 30 else "")

                await db.commit()

            if not agent_done_sent:
                await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info(f"[AgentWS] disconnected: user={user_id}, conv={conv_id}")
    except Exception as e:
        logger.error(f"[AgentWS] error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
