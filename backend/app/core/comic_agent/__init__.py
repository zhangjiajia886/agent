from .agent import ComicAgent, ComicRequest, ComicResult
from app.core.comfyui_client import comfyui_client
from app.core.llm_client import llm_client

comic_agent = ComicAgent(comfyui_client=comfyui_client, llm_client=llm_client)

__all__ = ["comic_agent", "ComicAgent", "ComicRequest", "ComicResult"]
