import re
from loguru import logger

from .workflow_selector import STYLE_PROMPTS

PROMPT_SYSTEM = "你是一个专业的 AI 图像生成提示词工程师，擅长将中文分镜描述转化为高质量的英文提示词。"

PROMPT_USER_TMPL = """将以下中文分镜描述转化为英文图像生成提示词：

分镜描述：{frame_desc}
风格基调：{style_base}
是否包含人脸：{has_face}

要求：
1. 用英文输出，不超过80个单词
2. 包含：人物描述 + 动作/表情 + 场景 + 光线/氛围 + 质量词（masterpiece, best quality）
3. 如果包含人脸，不要描述具体的人脸特征（由 InstantID 控制），只描述发型/服饰/动作
4. 不要负向提示词，只输出正向提示词
5. 直接输出提示词文本，不要有任何解释

输出示例：
xianxia style, 1girl from behind, standing at the foot of ethereal mountain, looking up at the peaks hidden in clouds, wide cinematic shot, golden hour lighting, masterpiece, best quality"""

NEGATIVE_PROMPTS = {
    "xianxia":  "ugly, deformed, blurry, bad anatomy, watermark, text, low quality, nsfw, modern clothing",
    "blindbox": "realistic, scary, ugly, deformed, text, watermark, low quality, dark, horror, nsfw",
    "ink":      "colorful, photorealistic, 3d render, western art, low quality, ugly, blurry, nsfw",
    "anime":    "ugly, deformed, bad anatomy, watermark, text, nsfw, low quality, blurry, realistic",
    "realistic": "ugly, deformed, blurry, bad anatomy, watermark, text, low quality, nsfw, cartoon",
}


async def build_prompt(
    frame_desc: str,
    style: str,
    has_face: bool,
    llm_client,
) -> tuple[str, str]:
    """返回 (positive_prompt, negative_prompt)"""
    style_base = STYLE_PROMPTS.get(style, STYLE_PROMPTS["xianxia"])
    messages = [
        {"role": "system", "content": PROMPT_SYSTEM},
        {
            "role": "user",
            "content": PROMPT_USER_TMPL.format(
                frame_desc=frame_desc,
                style_base=style_base,
                has_face="是（不描述具体人脸）" if has_face else "否",
            ),
        },
    ]
    try:
        positive = await llm_client.chat(messages)
        positive = positive.strip()
        positive = re.sub(r"^(输出|提示词|Prompt)[:：]?\s*", "", positive, flags=re.IGNORECASE)
        negative = NEGATIVE_PROMPTS.get(style, NEGATIVE_PROMPTS["xianxia"])
        return positive, negative
    except Exception as e:
        logger.warning(f"PromptBuilder LLM failed: {e}, using style base")
        fallback = f"{style_base}, {frame_desc[:30]}, masterpiece, best quality"
        return fallback, NEGATIVE_PROMPTS.get(style, "")


async def build_all_prompts(
    storyboard: list[str],
    style: str,
    has_face: bool,
    llm_client,
) -> list[tuple[str, str]]:
    results = []
    for frame_desc in storyboard:
        pos, neg = await build_prompt(frame_desc, style, has_face, llm_client)
        results.append((pos, neg))
    return results
