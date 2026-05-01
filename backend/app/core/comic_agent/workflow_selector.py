import copy
import json
import random
from pathlib import Path
from typing import Optional

from .workflow_registry import WORKFLOWS_ROOT, load_by_name, list_by_category

# ── 风格 → 首选工作流 name（按 DB name 格式）─────────────────────────────
# key: (style, has_face)  value: db workflow name
# face 工作流默认使用 SDXL-InstantID（已测试通过）
_FACE_DEFAULT = "SD图像系列__SDXL-InstantID面部一致"
_FACE_FACEID  = "SD图像系列__SDXL-IPA-FaceID面部一致"

T2I_STYLE_MAP = {
    ("xianxia",   False): "xianxia_basic",
    ("xianxia",   True):  _FACE_DEFAULT,
    ("blindbox",  False): "blindbox_q",
    ("blindbox",  True):  _FACE_DEFAULT,
    ("ink",       False): "moxin_ink",
    ("ink",       True):  _FACE_DEFAULT,
    ("anime",     False): "anime_basic",
    ("anime",     True):  _FACE_DEFAULT,
    ("realistic", False): "z_image_t2i",
    ("realistic", True):  _FACE_DEFAULT,
    # 新增高质量风格
    ("flux",      False): "Flux图像系列__Flux-fp16四件套文生图",
    ("flux",      True):  _FACE_FACEID,
    ("hidream",   False): "HiDream图像__HiDream-i1文生图",
    ("hidream",   True):  _FACE_DEFAULT,
    ("qwen",      False): "QwenImage图像系列__Qwen-Image-2512文生图-4步",
    ("qwen",      True):  _FACE_DEFAULT,
    ("sd15",      False): "SD图像系列__SD15-简单文生图",
    ("sd15",      True):  "SD图像系列__SD15-面部重绘",
    ("sdxl",      False): "SD图像系列__SDXL-ControlNet",
    ("sdxl",      True):  _FACE_DEFAULT,
    ("zimage",    False): "z_image_t2i",
    ("zimage",    True):  _FACE_DEFAULT,
}

I2V_DEFAULT = "wan_i2v"
T2V_DEFAULT = "Wan视频系列__Wan2_2-14B文生视频-4步"
EDIT_DEFAULT = "qwen_edit"
UPSCALE_DEFAULT = "其他图像__SeedVR2_简单图像高清放大"
AUDIO_DEFAULT   = "语音生成__音频分离"

STYLE_PROMPTS = {
    "xianxia": (
        "xianxia style, ancient chinese, elegant hanfu, ethereal mountain background, "
        "flowing sleeves, jade accessories, cinematic lighting, masterpiece, best quality"
    ),
    "blindbox": (
        "blindbox style, chibi, 3d render, cute big round eyes, pastel colors, "
        "clean white background, adorable expression, soft lighting, high quality, kawaii"
    ),
    "ink": (
        "ink wash painting, sumi-e, traditional chinese art style, "
        "monochrome with red accent, flowing brushstrokes, elegant composition, misty mountains"
    ),
    "anime": (
        "anime style, beautiful face, sparkling eyes, long flowing hair, "
        "xianxia outfit, soft lighting, clean linework, vibrant colors, masterpiece"
    ),
    "realistic": (
        "realistic, highly detailed, cinematic composition, beautiful lighting, "
        "masterpiece, best quality, 8k"
    ),
    "flux": (
        "high quality photo, sharp details, professional photography, natural lighting, "
        "masterpiece, best quality, 8k uhd"
    ),
}


def load_workflow(workflow_name: str) -> dict:
    """按工作流 name 加载 JSON（支持旧格式直接文件名和新格式 DB name）"""
    # 旧格式：直接文件名（无路径分隔符编码）
    simple = WORKFLOWS_ROOT / f"{workflow_name}.json"
    if simple.exists():
        return json.loads(simple.read_text(encoding="utf-8"))
    # 新格式：经过 registry 编码的 name
    return load_by_name(workflow_name)


def select_t2i(style: str, has_face: bool = False) -> str:
    key = (style, has_face)
    return T2I_STYLE_MAP.get(key, T2I_STYLE_MAP.get((style, False), "xianxia_basic"))


def select_workflow(style: str, has_face: bool) -> str:
    """向后兼容的接口"""
    return select_t2i(style, has_face)


def select_edit(style: Optional[str] = None) -> str:
    if style == "qwen":
        return "QwenImage图像系列__Qwen-Image-Edit2511-材质替换"
    if style == "flux":
        return "Flux图像系列__Flux2图像编辑"
    return EDIT_DEFAULT


def select_i2v(style: Optional[str] = None) -> str:
    if style == "wan_fun":
        return "Wan视频系列__Wan2_2-14B-Fun控制版"
    if style == "wan_endframe":
        return "Wan视频系列__Wan2_2首尾帧视频_4步"
    return I2V_DEFAULT


def select_t2v(style: Optional[str] = None) -> str:
    if style == "wan_anime":
        return "WAN_2_2-动漫-4090-工作流"
    if style == "wan_transparent":
        return "Wan视频系列__Wan2_1文生视频-透明底视频"
    return T2V_DEFAULT


def select_upscale() -> str:
    return UPSCALE_DEFAULT


def inject_params(
    workflow: dict,
    positive_prompt: str = "",
    negative_prompt: str = "",
    seed: int = -1,
    width: Optional[int] = None,
    height: Optional[int] = None,
    lora_strength: Optional[float] = None,
    instruction: Optional[str] = None,
    edit_image: Optional[str] = None,
    source_image: Optional[str] = None,
    num_frames: Optional[int] = None,
) -> dict:
    wf = copy.deepcopy(workflow)
    if seed == -1:
        seed = random.randint(0, 2**31)

    # 剔除元数据键
    node_items = [(k, v) for k, v in wf.items() if not k.startswith("__")]

    for node_id, node in node_items:
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        if ct == "CLIPTextEncode":
            if inputs.get("text") == "POSITIVE_PROMPT" and positive_prompt:
                inputs["text"] = positive_prompt
            elif inputs.get("text") == "NEGATIVE_PROMPT" and negative_prompt:
                inputs["text"] = negative_prompt

        elif ct in ("KSampler", "KSamplerSelect"):
            inputs["seed"] = seed

        elif ct == "KSamplerAdvanced":
            if inputs.get("add_noise") == "enable":
                inputs["noise_seed"] = seed

        elif ct in ("EmptyLatentImage", "EmptySD3LatentImage",
                    "EmptyHunyuanLatentVideo", "EmptyLTXVLatentVideo"):
            if width:
                inputs["width"] = width
            if height:
                inputs["height"] = height
            if num_frames and "length" in inputs:
                inputs["length"] = num_frames
            if num_frames and "num_frames" in inputs:
                inputs["num_frames"] = num_frames

        elif ct == "LoadImage":
            img = source_image or edit_image
            if img:
                inputs["image"] = img

        elif ct in ("TextEncodeQwenImageEditPlus", "TextEncodeQwenImage"):
            if instruction:
                inputs["prompt"] = instruction
            elif positive_prompt:
                inputs["prompt"] = positive_prompt

        elif ct == "CLIPTextEncodeFlux":
            if positive_prompt:
                inputs["clip_l"] = positive_prompt
                inputs["t5xxl"] = positive_prompt

        elif ct == "WanTextEncode":
            if positive_prompt:
                inputs["positive"] = positive_prompt
            if negative_prompt:
                inputs["negative"] = negative_prompt

        elif ct == "LoraLoader" and lora_strength is not None:
            inputs["strength_model"] = lora_strength
            inputs["strength_clip"] = lora_strength

        elif ct == "RandomNoise":
            inputs["noise_seed"] = seed

        elif ct == "ModelSamplingFlux":
            pass

    return wf
