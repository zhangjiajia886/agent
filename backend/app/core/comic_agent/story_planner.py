import json
import re
from loguru import logger

STORY_SYSTEM = "你是一个专业的漫剧分镜设计师，擅长将故事拆分为视觉化的分镜描述。"

STORY_USER_TMPL = """为以下漫剧生成{num_frames}格分镜描述：
- 风格：{style_zh}
- 故事：{story}
- 情感基调：{mood_zh}

要求：
1. 遵循"起承转合"结构（{num_frames}格均匀分配）
2. 每格描述包含：景别（远景/中景/近景）、人物动作/状态、场景氛围
3. 描述简洁，每格不超过30字
4. 用中文描述

以 JSON 数组返回（纯 JSON，无其他文字）：
["格1描述", "格2描述", ...]"""

STYLE_ZH = {
    "xianxia": "仙侠国风",
    "blindbox": "盲盒Q版",
    "ink": "水墨国画",
    "anime": "二次元动漫",
    "realistic": "写实漫画",
}

MOOD_ZH = {
    "epic": "史诗壮阔",
    "cute": "萌系可爱",
    "dramatic": "戏剧张力",
    "peaceful": "平和宁静",
}


async def plan_storyboard(
    story: str,
    num_frames: int,
    style: str,
    mood: str,
    llm_client,
) -> list[str]:
    messages = [
        {"role": "system", "content": STORY_SYSTEM},
        {
            "role": "user",
            "content": STORY_USER_TMPL.format(
                num_frames=num_frames,
                style_zh=STYLE_ZH.get(style, style),
                story=story,
                mood_zh=MOOD_ZH.get(mood, mood),
            ),
        },
    ]
    try:
        raw = await llm_client.chat(messages)
        raw = raw.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            raw = match.group(0)
        frames = json.loads(raw)
        while len(frames) < num_frames:
            frames.append(f"格{len(frames)+1}：场景延续")
        return frames[:num_frames]
    except Exception as e:
        logger.warning(f"StoryPlanner LLM failed: {e}, using placeholder frames")
        return [f"格{i+1}：{story}场景{i+1}" for i in range(num_frames)]
