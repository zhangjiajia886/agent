"""Diagram rendering proxy — mermaid.ink (primary) + kroki.io (fallback)."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
import base64
import json as _json

router = APIRouter(prefix="/api/diagram", tags=["diagram"])

KROKI_BASE = "https://kroki.io"
MERMAID_INK_BASE = "https://mermaid.ink"
ALLOWED_TYPES = {"plantuml", "graphviz", "diagramsnet", "mermaid", "bpmn", "ditaa", "c4plantuml"}


class DiagramRequest(BaseModel):
    diagram_type: str
    source: str


async def _render_mermaid_ink(source: str) -> bytes:
    """Render mermaid via mermaid.ink (GET /svg/<base64url_of_json>)."""
    state = base64.urlsafe_b64encode(
        _json.dumps({"code": source, "mermaid": {"theme": "default"}}).encode()
    ).rstrip(b"=").decode()
    async with httpx.AsyncClient(timeout=20, verify=False) as client:
        resp = await client.get(
            f"{MERMAID_INK_BASE}/svg/{state}",
            headers={"Accept": "image/svg+xml"},
        )
    if resp.status_code != 200:
        raise httpx.RequestError(f"mermaid.ink returned {resp.status_code}")
    return resp.content


async def _render_via_kroki(diagram_type: str, source: str) -> bytes:
    async with httpx.AsyncClient(timeout=20, verify=False) as client:
        resp = await client.post(
            f"{KROKI_BASE}/{diagram_type}/svg",
            content=source.encode(),
            headers={"Content-Type": "text/plain", "Accept": "image/svg+xml"},
        )
    if resp.status_code != 200:
        raise httpx.RequestError(f"Kroki returned {resp.status_code}: {resp.text[:200]}")
    return resp.content


async def _render(diagram_type: str, source: str) -> bytes:
    """Try mermaid.ink first for mermaid, then kroki.io for all types."""
    if diagram_type == "mermaid":
        try:
            return await _render_mermaid_ink(source)
        except Exception:
            pass  # fall through to kroki
    try:
        return await _render_via_kroki(diagram_type, source)
    except httpx.RequestError as e:
        raise HTTPException(502, f"渲染失败 (mermaid.ink + kroki.io 均不可达): {e}")


@router.get("/view")
async def view_diagram(
    type: str = Query(..., description="图表类型: mermaid/plantuml/graphviz/diagramsnet"),
    src: str = Query(..., description="Base64url 编码的图表源码"),
):
    if type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的类型: {type}")
    try:
        source = base64.urlsafe_b64decode(src + "==").decode()
    except Exception:
        raise HTTPException(400, "src 参数解码失败，需为 base64url 编码")
    svg = await _render(type, source)
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.post("/render")
async def render_diagram(req: DiagramRequest):
    if req.diagram_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"不支持的图表类型: {req.diagram_type}，允许: {ALLOWED_TYPES}")
    svg = await _render(req.diagram_type, req.source)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
