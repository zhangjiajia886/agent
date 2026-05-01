import json
import re
from loguru import logger

INTENT_SYSTEM = "你是一个专业的漫剧生成助手，负责理解用户的创作需求。"

INTENT_USER_TMPL = """分析以下用户描述，提取关键信息，以 JSON 格式返回：

用户描述：{description}

返回格式（纯 JSON，无其他文字）：
{{
  "style": "风格，必须是以下之一：xianxia（仙侠）/ blindbox（盲盒Q版）/ ink（水墨）/ anime（动漫）/ realistic（写实漫）",
  "story": "核心故事情节，用中文简短描述（20字以内）",
  "need_face": true或false（用户提到保留人脸/这张脸/人物特征时为true）,
  "mood": "情感基调：epic（史诗）/ cute（可爱）/ dramatic（戏剧）/ peaceful（平和）",
  "num_frames": 推断的格数，整数，1到8，默认4
}}"""


async def parse_intent(description: str, llm_client) -> dict:
    messages = [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": INTENT_USER_TMPL.format(description=description)},
    ]
    try:
        raw = await llm_client.chat(messages)
        raw = raw.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            raw = match.group(0)
        result = json.loads(raw)
        result.setdefault("style", "xianxia")
        result.setdefault("story", description[:20])
        result.setdefault("need_face", False)
        result.setdefault("mood", "epic")
        result.setdefault("num_frames", 4)
        return result
    except Exception as e:
        logger.warning(f"IntentParser LLM failed: {e}, using defaults")
        return {
            "style": "xianxia",
            "story": description[:20],
            "need_face": False,
            "mood": "epic",
            "num_frames": 4,
        }
