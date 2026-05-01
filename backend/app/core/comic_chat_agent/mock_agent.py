"""
Mock Agent：后端 Mock 模式，模拟 Agent 分析 → 工具调用 → 生成结果 的完整事件流。
后端就绪后替换为真实 Claude API 调用。
"""
import asyncio
import random
import time
from typing import AsyncIterator

from loguru import logger


STYLE_DETECT = {
    "仙侠": "xianxia", "修仙": "xianxia", "仙山": "xianxia", "仙灵": "xianxia",
    "水墨": "ink", "国画": "ink", "山水": "ink",
    "盲盒": "blindbox", "Q版": "blindbox", "可爱": "blindbox",
    "动漫": "anime", "二次元": "anime", "樱花": "anime",
    "写实": "realistic", "真实": "realistic",
}

STYLE_NAMES = {
    "xianxia": "仙侠", "ink": "水墨", "blindbox": "盲盒Q版",
    "anime": "动漫", "realistic": "写实",
}

MOCK_PROMPTS = {
    "xianxia": [
        "wide shot, mystical mountain island, mist and bamboo, cinematic",
        "medium shot, young swordsman on bamboo forest path, rain drops",
        "close-up, maiden sleeping by lotus pond, petals scattered, ethereal",
        "two-shot, swordsman and maiden meeting, cherry blossoms falling",
        "wide shot, dramatic mountain peaks, sword in ground, epic sky",
        "close-up, maiden smiling, wind in hair, golden light",
    ],
    "ink": [
        "ink wash painting, distant mountains, lone fisherman on river",
        "ink style, scholar under willow, reading scroll",
        "ink, mysterious woman on stone bridge, rain, umbrella",
        "ink wash, full moon over temple, warm lanterns",
    ],
    "blindbox": [
        "chibi girl opening mystery gift box, sparkles, kawaii",
        "chibi boy surprised face, confetti, pastel colors",
        "two chibi characters hugging, hearts floating, cute",
        "chibi girl jumping with joy, rainbow, pop art",
    ],
    "anime": [
        "anime, cherry blossom trees, school gate, spring morning",
        "anime, girl with long hair walking, sunset, melancholic",
        "anime close-up, boy and girl eyes meeting, sakura petals",
        "anime wide shot, rooftop, city skyline at dusk, wind",
    ],
    "realistic": [
        "photorealistic, young woman in garden, soft natural light",
        "realistic, man standing by window, morning sunlight, cinematic",
        "hyper-realistic, couple walking autumn path, falling leaves",
        "realistic portrait, woman reading book in cafe, warm tones",
    ],
}


def _detect_style(text: str) -> str:
    for kw, style in STYLE_DETECT.items():
        if kw in text:
            return style
    return random.choice(list(MOCK_PROMPTS.keys()))


def _detect_frames(text: str) -> int:
    import re
    m = re.search(r"(\d)\s*格", text)
    if m:
        return max(2, min(6, int(m[1])))
    return 4


async def mock_agent_stream(
    message: str,
    style_override: str = "auto",
    frames_override: int = 0,
) -> AsyncIterator[dict]:
    """
    模拟 Agent 对话流，yield JSON 事件。
    与前端 AgentEvent 格式完全对齐：
      { type: "text" | "tool_start" | "tool_done" | "error", ... }
    """
    style = style_override if style_override != "auto" else _detect_style(message)
    num_frames = frames_override if frames_override > 0 else _detect_frames(message)
    style_name = STYLE_NAMES.get(style, style)
    prompts = MOCK_PROMPTS.get(style, MOCK_PROMPTS["xianxia"])

    logger.info(f"[MockAgent] start: style={style}, frames={num_frames}, msg={message[:30]}...")

    # Step 1: 分析回复
    await asyncio.sleep(0.4)
    yield {
        "type": "text",
        "content": (
            f"好的！我来分析这段故事。\n\n"
            f"**风格判断**：{style_name}风格\n"
            f"**分镜规划**：{num_frames} 格\n\n"
            f"开始逐格生成..."
        ),
    }

    # Step 2~N: 逐格生成
    for i in range(num_frames):
        prompt = prompts[i % len(prompts)]

        await asyncio.sleep(0.5)
        yield {
            "type": "tool_start",
            "tool": "generate_image",
            "input": {"prompt": prompt, "style": style, "width": 1024, "height": 1024, "seed": -1},
        }

        gen_time = 1.0 + random.random() * 1.5
        await asyncio.sleep(gen_time)

        seed = random.randint(1, 99999)
        img_url = f"https://picsum.photos/seed/{seed}/512/512"
        yield {
            "type": "tool_done",
            "tool": "generate_image",
            "result": f"图像已生成，路径: {img_url}",
        }

        if i < num_frames - 1:
            await asyncio.sleep(0.3)
            yield {
                "type": "text",
                "content": f"第 {i + 1} 格完成 ✓ 正在生成第 {i + 2} 格...",
            }

    # Final
    await asyncio.sleep(0.3)
    yield {
        "type": "text",
        "content": (
            f"🎉 **{num_frames} 格{style_name}风格漫剧全部生成完毕！**\n\n"
            f"需要我把某一格动态化吗？或者对某一格不满意需要重新生成？"
        ),
    }
    logger.info(f"[MockAgent] done: {num_frames} frames generated")
