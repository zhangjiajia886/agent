"""draw_diagram — renders a diagram and returns a Markdown image link."""
from __future__ import annotations

import base64
from typing import Any

from .base import BaseTool

KROKI_TYPE_MAP = {
    "mermaid": "mermaid",
    "plantuml": "plantuml",
    "graphviz": "graphviz",
    "dot": "graphviz",
    "drawio": "diagramsnet",
    "xml": "diagramsnet",
}

SUPPORTED = ", ".join(KROKI_TYPE_MAP.keys())


class DrawDiagramTool(BaseTool):
    name = "draw_diagram"
    description = (
        "将图表源码渲染为图片并返回 Markdown 图片链接，前端直接显示。"
        f"支持类型: {SUPPORTED}。"
        "用户要求画流程图、架构图、时序图、ER图、类图等时使用此工具。"
    )
    category = "diagram"
    risk_level = "low"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "diagram_type": {
                    "type": "string",
                    "description": f"图表类型，可选: {SUPPORTED}",
                },
                "code": {
                    "type": "string",
                    "description": "图表源码（Mermaid/PlantUML/Graphviz DOT/draw.io XML 语法）",
                },
                "title": {
                    "type": "string",
                    "description": "图表标题（可选，用于图片 alt 文本）",
                    "default": "diagram",
                },
            },
            "required": ["diagram_type", "code"],
        }

    def is_read_only(self) -> bool:
        return True

    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        dtype = arguments.get("diagram_type", "mermaid").lower()
        code = arguments.get("code", "").strip()
        title = arguments.get("title", "diagram")

        kroki_type = KROKI_TYPE_MAP.get(dtype, dtype)

        # Encode source as base64url for the view endpoint
        src_b64 = base64.urlsafe_b64encode(code.encode()).decode().rstrip("=")
        url = f"/api/diagram/view?type={kroki_type}&src={src_b64}"

        markdown_img = f"![{title}]({url})"
        return {
            "output": markdown_img,
            "diagram_url": url,
            "diagram_type": kroki_type,
        }
