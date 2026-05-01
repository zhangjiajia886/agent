"""
WorkflowRegistry: 自动扫描 workflows/ 目录，按文件名/路径规则分类所有工作流。
供 seed_agent_data 和 workflow_selector 使用。
"""
import json
from pathlib import Path
from typing import Optional

WORKFLOWS_ROOT = Path(__file__).parent / "workflows"

# subgraph 标记关键词（含在文件名中则标记为 disabled）
_SUBGRAPH_KW = [
    "Klein", "LTX2图生视频", "Layered图层分解", "Imag-Eedit-2509",
    "S2V音频驱动", "Animate-角色动画",
]


def _is_subgraph(path: Path, data: dict) -> bool:
    if data.get("__has_subgraph"):
        return True
    return any(kw in path.name for kw in _SUBGRAPH_KW)


def _detect_category(path: Path) -> str:
    name = path.stem
    parts_str = "/".join(path.parts)

    if any(k in name for k in ["音频分离", "音频处理", "语音分离"]):
        return "audio"

    if any(k in name for k in ["超分辨率", "高清放大", "超分", "SeedVR"]):
        return "upscale"

    if any(k in name for k in ["面部重绘", "FaceID", "InstantID", "instantid"]):
        return "face"

    if any(k in name for k in ["图生视频", "图像加音频到视频", "首尾帧视频",
                                 "S2V", "角色动画", "Fun控制版"]):
        return "i2v"

    if any(k in name for k in ["文生视频", "透明底视频"]):
        return "t2v"

    # WAN 2.2 动漫工作流（根目录无子分类，属于视频）
    if "动漫" in name and any(v in parts_str for v in ["视频", "WAN", "Wan"]):
        return "t2v"

    if any(k in name for k in ["图像编辑", "图片编辑", "局部清除", "扩图",
                                 "图生图", "材质替换", "光源统一", "Repaint",
                                 "Kontext", "图像反推", "图层分解"]):
        return "edit"

    if any(k in name for k in ["Edit", "edit"]) and "文生图" not in name:
        return "edit"

    if any(k in parts_str for k in ["视频系列", "Wan视频", "KJ视频", "LTX2视频"]):
        return "i2v"

    return "t2i"


def _detect_style(path: Path) -> Optional[str]:
    full = str(path)
    name = path.stem

    if "双截棍-RTX5090" in full:
        return "nunchaku_fp4"
    if "双截棍-非RTX5090" in full:
        return "nunchaku_int4"
    if "Flux" in full or "flux" in full:
        return "flux"
    if "HiDream" in full:
        return "hidream"
    if "LTX" in full:
        return "ltx"
    if "Qwen" in full:
        return "qwen"
    if "SDXL" in full:
        return "sdxl"
    if "SD15" in full:
        return "sd15"
    if "Z-Image" in full or "z_image" in name:
        return "zimage"
    if "Wan" in full or "WAN" in full or "wan" in name:
        return "wan"
    if "xianxia" in name:
        return "xianxia"
    if "anime" in name:
        return "anime"
    if "blindbox" in name:
        return "blindbox"
    if "moxin" in name or "ink" in name:
        return "ink"
    return None


def _make_name(rel: Path) -> str:
    """相对路径 → DB 唯一 name（≤100 字符）"""
    s = str(rel.with_suffix(""))
    s = s.replace("/", "__").replace(" ", "_").replace(".", "_")
    return s[:100]


def scan_all() -> list[dict]:
    """扫描 workflows/ 目录，返回所有工作流的元数据列表（用于 seed）"""
    results = []
    for json_path in sorted(WORKFLOWS_ROOT.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        rel = json_path.relative_to(WORKFLOWS_ROOT)
        is_sg = _is_subgraph(json_path, data)
        cat = _detect_category(json_path)
        style = _detect_style(json_path)

        results.append({
            "name": _make_name(rel),
            "display_name": json_path.stem,
            "category": cat,
            "style_tag": style,
            "is_enabled": not is_sg,
            "description": "subgraph：含子图节点，不可直接提交" if is_sg else None,
            "_file_path": str(rel),
        })
    return results


_NAME_CACHE: dict[str, Path] | None = None


def _get_name_cache() -> dict[str, Path]:
    """延迟构建 name → 绝对路径 映射（与 _make_name 完全一致）"""
    global _NAME_CACHE
    if _NAME_CACHE is None:
        _NAME_CACHE = {}
        for p in WORKFLOWS_ROOT.rglob("*.json"):
            rel = p.relative_to(WORKFLOWS_ROOT)
            _NAME_CACHE[_make_name(rel)] = p
    return _NAME_CACHE


def load_by_name(wf_name: str) -> dict:
    """按 DB name 加载 workflow JSON"""
    # 1. 精确匹配缓存（解决 . 和空格不可逆问题）
    cache = _get_name_cache()
    if wf_name in cache:
        return json.loads(cache[wf_name].read_text(encoding="utf-8"))

    # 2. 旧式直接路径还原
    candidate = wf_name.replace("__", "/").replace("_", " ") + ".json"
    p = WORKFLOWS_ROOT / candidate
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))

    raise FileNotFoundError(f"Workflow file not found for name={wf_name!r}")


def list_by_category(category: str, enabled_only: bool = True) -> list[dict]:
    """返回指定分类的所有工作流元数据"""
    return [w for w in scan_all()
            if w["category"] == category
            and (not enabled_only or w["is_enabled"])]
