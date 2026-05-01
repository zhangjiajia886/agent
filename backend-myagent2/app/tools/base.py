from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base interface for all tools (built-in and MCP)."""

    name: str = ""
    description: str = ""
    category: str = "general"
    risk_level: str = "low"  # low | medium | high

    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    async def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool and return result."""
        ...

    def is_read_only(self) -> bool:
        return False

    def is_concurrency_safe(self) -> bool:
        return self.is_read_only()
