"""
Smart Agent：基于意图分类的对话流。
- 普通聊天 → 友好文字回复，不走图片流程
- 图片/漫剧/视频 → 选工作流 → 发 tool 事件 + image_url
- thinking 事件：让前端显示思考过程
"""
import asyncio
import random
import re
from typing import AsyncIterator

from loguru import logger

# ── 意图关键词（顺序即优先级） ──────────────────────────────────────────
_INTENT_KW = [
    ("upscale", ["超分", "放大图", "高清放大", "提高分辨率", "upscale"]),
    ("edit",    ["编辑图片", "修改图片", "改图", "图像编辑", "图片编辑", "局部修改"]),
    ("i2v",     ["图生视频", "动起来", "动态化", "图片变视频", "图片动画", "图生动"]),
    ("t2v",     ["文生视频", "生成视频", "视频制作", "文字生视频", "做个视频"]),
    ("t2i",     ["生成图片", "画一张", "画一幅", "画个", "创作图片", "文生图",
                  "生成一张", "给我画", "帮我画", "画出"]),
    ("comic",   ["漫剧", "漫画", "故事", "分镜", "分格", "格漫", "连环",
                  "连续故事", "四格", "六格", "两格", "3格", "4格", "5格", "6格"]),
    ("chat",    ["你好", "hello", "嗨", "hi ", "介绍", "谢谢", "感谢",
                  "你是什么", "你是谁", "你叫什么", "你能做什么",
                  "能做什么", "功能", "帮助", "使用说明", "能干嘛",
                  "好的", "知道了", "明白了", "再见", "bye"]),
    ("chat",    []),  # fallback slot
]

# ── 风格检测 ───────────────────────────────────────────────────────────
_STYLE_KW = {
    "xianxia":  ["仙侠", "修仙", "仙山", "仙灵", "古风", "仙境", "剑侠"],
    "ink":      ["水墨", "国画", "山水", "水墨画"],
    "blindbox": ["盲盒", "Q版", "q版", "可爱", "萌"],
    "anime":    ["动漫", "二次元", "樱花", "动画"],
    "realistic":["写实", "真实", "摄影", "照片"],
    "flux":     ["flux", "Flux", "高质量", "hd", "HD"],
}

_STYLE_NAMES = {
    "xianxia":  "仙侠古风", "ink":      "水墨国画",
    "blindbox": "盲盒Q版",  "anime":    "动漫二次元",
    "realistic":"写实摄影",  "flux":     "Flux 高质量",
}

_MOCK_PROMPTS = {
    "xianxia": [
        "mystical mountain island, mist and bamboo, ancient chinese, cinematic masterpiece",
        "young swordsman on bamboo forest path, rain drops, ethereal light, best quality",
        "maiden sleeping by lotus pond, petals scattered, soft glow, ethereal",
        "swordsman and maiden meeting, cherry blossoms falling, golden sunset",
        "dramatic mountain peaks, sword in ground, epic sky, xianxia style",
        "smiling maiden, wind in hair, flowing hanfu, golden light, masterpiece",
    ],
    "ink": [
        "ink wash painting, distant mountains, lone fisherman on river",
        "ink style, scholar under willow, reading scroll by candlelight",
        "mysterious woman on stone bridge, rain, holding umbrella, ink wash",
        "ink wash, full moon over temple, warm lanterns reflecting in water",
    ],
    "blindbox": [
        "chibi girl opening mystery gift box, sparkles, kawaii 3d render pastel",
        "chibi boy surprised face, confetti, pastel colors, cute 3d",
        "two chibi characters hugging, hearts floating, kawaii render",
        "chibi girl jumping with joy, rainbow background, pop art 3d",
    ],
    "anime": [
        "anime, cherry blossom trees, school gate, spring morning, beautiful masterpiece",
        "anime girl with long hair walking, sunset, melancholic mood, high quality",
        "anime close-up, boy and girl eyes meeting, sakura petals falling",
        "anime wide shot, rooftop, city skyline at dusk, gentle wind",
    ],
    "realistic": [
        "photorealistic, young woman in garden, soft natural light, sharp detail 8k",
        "realistic, man standing by window, morning sunlight, cinematic",
        "hyper-realistic, couple walking autumn path, falling leaves, 8k uhd",
        "realistic portrait, woman reading book in cafe, warm tones, bokeh",
    ],
    "flux": [
        "ultra high quality portrait, stunning detail, professional photo, 8k uhd",
        "ultra-detailed scene, masterpiece quality, professional cinematic lighting",
        "photorealistic rendering, cinematic, award-winning photography, sharp focus",
    ],
}

_CHAT_REPLIES = {
    "greeting": (
        "你好，我是 **漫剧 Agent**。\n\n"
        "我可以协助你完成以下创作任务：\n"
        "- **文生图**：根据描述生成多种风格的视觉内容\n"
        "- **漫剧创作**：完成多格分镜、连环叙事与画面生成\n"
        "- **文生视频 / 图生视频**：将创意进一步动态化呈现\n"
        "- **图像编辑 / 超分处理**：对现有图片进行修改与质量提升\n\n"
        "**支持风格：** 仙侠 · 水墨 · 盲盒 Q 版 · 动漫 · 写实 · Flux\n\n"
        "例如，你可以这样发起任务：\n"
        "「仙侠风格 4 格漫剧，一位白衣剑客踏雪而来」"
    ),
    "help": (
        "**使用指南：**\n\n"
        "| 意图 | 示例 |\n"
        "|------|------|\n"
        "| 漫剧生成 | 水墨4格漫剧，书生在溪边遇见仙女 |\n"
        "| 文生图 | 画一张动漫风格的樱花街道少女 |\n"
        "| 文生视频 | 生成一段仙侠风景视频 |\n"
        "| 图生视频 | 让这张图动起来（请上传图片） |\n"
        "| 图像编辑 | 把图片里的背景改成夜晚 |\n\n"
        "**风格关键词：** 仙侠 / 水墨 / 盲盒 / 动漫 / 写实 / Flux"
    ),
    "thanks": "不客气。如需继续创作或调整效果，随时告诉我。",
    "bye": "好的，期待下次继续为你完成创作任务。",
    "default": (
        "我已理解你的需求。\n"
        "如果你希望继续推进图片或漫剧创作，可以直接说明题材、风格与核心画面，例如：\n\n"
        "「**动漫风格**的清晨樱花街道，少女骑着自行车经过」"
    ),
}


def _detect_intent(text: str) -> str:
    t_low = text.lower()
    for intent, kws in _INTENT_KW:
        if any(kw.lower() in t_low for kw in kws):
            return intent
    if len(text.strip()) > 10:
        return "comic"
    return "chat"


def _detect_style(text: str, override: str = "auto") -> str:
    if override != "auto":
        return override
    for style, kws in _STYLE_KW.items():
        if any(kw in text for kw in kws):
            return style
    return random.choice(["xianxia", "anime", "realistic"])


def _detect_frames(text: str, override: int = 0) -> int:
    if override > 0:
        return max(2, min(6, override))
    m = re.search(r"([2-6])\s*格", text)
    if m:
        return int(m[1])
    return 4


def _chat_reply(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["你好", "hello", "hi ", "嗨", "早上好", "下午好", "大家好"]):
        return _CHAT_REPLIES["greeting"]
    if any(k in t for k in ["你是什么", "你是谁", "你叫什么", "你能做什么",
                              "自我介绍", "介绍一下你"]):
        return _CHAT_REPLIES["greeting"]
    if any(k in t for k in ["帮助", "功能", "能做什么", "使用说明", "怎么用", "能干嘛"]):
        return _CHAT_REPLIES["help"]
    if any(k in t for k in ["谢谢", "感谢", "多谢", "thanks"]):
        return _CHAT_REPLIES["thanks"]
    if any(k in t for k in ["再见", "bye", "拜拜", "退出"]):
        return _CHAT_REPLIES["bye"]
    return _CHAT_REPLIES["default"]


async def smart_agent_stream(
    message: str,
    style_override: str = "auto",
    frames_override: int = 0,
) -> AsyncIterator[dict]:
    """
    智能 Agent 对话流，根据意图分发不同处理路径。
    事件类型: thinking | text | tool_start | tool_done | error
    tool_done 额外字段: image_url, duration
    """
    intent = _detect_intent(message)
    logger.info(f"[SmartAgent] intent={intent!r} msg={message[:40]!r}")

    # ── 普通聊天 ──────────────────────────────────────────────────────
    if intent == "chat":
        await asyncio.sleep(0.15)
        yield {"type": "thinking", "content": "已识别为对话类请求，正在组织回复内容。"}
        await asyncio.sleep(0.2)
        yield {"type": "text", "content": _chat_reply(message)}
        return

    # ── 公共参数解析 ─────────────────────────────────────────────────
    style = _detect_style(message, style_override)
    style_name = _STYLE_NAMES.get(style, style)
    prompts = _MOCK_PROMPTS.get(style, _MOCK_PROMPTS["xianxia"])

    # ── 图生视频 ─────────────────────────────────────────────────────
    if intent == "i2v":
        yield {"type": "thinking", "content": "已识别为图生视频任务，正在准备对应工作流。"}
        await asyncio.sleep(0.3)
        yield {"type": "text", "content": "请上传需要动态化处理的图片，并补充期望的运动效果或镜头描述。"}
        return

    # ── 文生视频 ─────────────────────────────────────────────────────
    if intent == "t2v":
        yield {"type": "thinking", "content": f"已识别为文生视频任务。\n目标风格：{style_name}\n正在准备生成流程。"}
        await asyncio.sleep(0.4)
        yield {"type": "text", "content": f"正在生成 **{style_name}** 风格视频，请稍候。"}
        await asyncio.sleep(0.2)
        yield {"type": "tool_start", "tool": "text_to_video",
               "input": {"prompt": message, "style": style}}
        t = 1.8 + random.random()
        await asyncio.sleep(t)
        yield {"type": "tool_done", "tool": "text_to_video",
               "result": "视频已生成", "duration": round(t, 1)}
        yield {"type": "text", "content": "视频生成已完成。如需调整镜头语言、动作强度或整体风格，我可以继续优化。"}
        return

    # ── 图像编辑 ─────────────────────────────────────────────────────
    if intent == "edit":
        yield {"type": "thinking", "content": "已识别为图像编辑任务，正在准备编辑流程。"}
        await asyncio.sleep(0.3)
        yield {"type": "text", "content": "请上传需要编辑的图片，并明确说明希望修改的内容。"}
        return

    # ── 超分辨率 ─────────────────────────────────────────────────────
    if intent == "upscale":
        yield {"type": "thinking", "content": "已识别为图像增强任务，正在准备超分流程。"}
        await asyncio.sleep(0.3)
        yield {"type": "text", "content": "请上传需要进行超分增强的图片。"}
        return

    # ── 单图生成 ─────────────────────────────────────────────────────
    if intent == "t2i":
        yield {
            "type": "thinking",
            "content": (
                f"任务类型：文生图\n"
                f"目标风格：{style_name}\n"
                f"执行工作流：{style}_t2i\n"
                f"当前状态：正在生成首版结果。"
            ),
        }
        await asyncio.sleep(0.3)
        yield {"type": "text", "content": f"已开始生成 **{style_name}** 风格图片。\n"}
        await asyncio.sleep(0.2)
        prompt = prompts[0]
        yield {"type": "tool_start", "tool": "generate_image",
               "input": {"prompt": prompt, "style": style, "width": 1024, "height": 1024}}
        t = 1.5 + random.random() * 1.5
        await asyncio.sleep(t)
        seed = random.randint(100, 99999)
        yield {
            "type": "tool_done", "tool": "generate_image",
            "result": "图像已生成",
            "image_url": f"https://picsum.photos/seed/{seed}/800/800",
            "duration": round(t, 1),
        }
        yield {"type": "text", "content": "图片生成已完成。如需重绘、换风格或继续精修，请直接告诉我。"}
        return

    # ── 漫剧生成（comic / 默认） ───────────────────────────────────────
    num_frames = _detect_frames(message, frames_override)
    yield {
        "type": "thinking",
        "content": (
            f"任务类型：漫剧生成\n"
            f"风格识别：{style_name}\n"
            f"分镜规划：{num_frames} 格\n"
            f"执行工作流：{style}_basic\n"
            f"当前状态：逐格生成中。"
        ),
    }
    await asyncio.sleep(0.5)
    yield {
        "type": "text",
        "content": f"已开始生成 **{style_name}** 风格 **{num_frames}** 格漫剧。\n",
    }

    for i in range(num_frames):
        prompt = prompts[i % len(prompts)]
        if i > 0:
            await asyncio.sleep(0.15)
            yield {
                "type": "thinking",
                "content": f"正在处理第 {i+1}/{num_frames} 格，画面摘要：{prompt[:50]}...",
            }
        await asyncio.sleep(0.25)
        yield {
            "type": "tool_start", "tool": "generate_image",
            "input": {"prompt": prompt, "style": style, "frame": i + 1},
        }
        t = 0.8 + random.random() * 1.2
        await asyncio.sleep(t)
        seed = random.randint(100, 99999)
        yield {
            "type": "tool_done", "tool": "generate_image",
            "result": f"第 {i + 1} 格已生成",
            "image_url": f"https://picsum.photos/seed/{seed}/768/768",
            "duration": round(t, 1),
        }

    await asyncio.sleep(0.25)
    yield {
        "type": "text",
        "content": (
            f"**{num_frames} 格 {style_name} 漫剧已生成完成。**\n\n"
            f"如果你需要对某一格继续优化、替换，或进一步制作成动态视频，我可以继续处理。"
        ),
    }
    logger.info(f"[SmartAgent] done: intent={intent}, style={style}, frames={num_frames}")
