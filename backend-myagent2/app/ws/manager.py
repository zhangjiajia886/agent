from __future__ import annotations

import json
import asyncio
from typing import Any
from fastapi import WebSocket


class WSManager:
    """WebSocket connection manager for real-time execution events."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._global_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket, execution_id: str | None = None) -> None:
        await ws.accept()
        if execution_id:
            self._connections.setdefault(execution_id, []).append(ws)
        else:
            self._global_connections.append(ws)

    def disconnect(self, ws: WebSocket, execution_id: str | None = None) -> None:
        if execution_id and execution_id in self._connections:
            self._connections[execution_id] = [
                c for c in self._connections[execution_id] if c is not ws
            ]
            if not self._connections[execution_id]:
                del self._connections[execution_id]
        else:
            self._global_connections = [c for c in self._global_connections if c is not ws]

    async def emit(self, event_type: str, data: dict[str, Any], execution_id: str | None = None) -> None:
        message = json.dumps({"type": event_type, **data}, ensure_ascii=False, default=str)
        targets: list[WebSocket] = []
        if execution_id and execution_id in self._connections:
            targets.extend(self._connections[execution_id])
        targets.extend(self._global_connections)

        disconnected: list[tuple[WebSocket, str | None]] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                eid = execution_id if ws in self._connections.get(execution_id or "", []) else None
                disconnected.append((ws, eid))

        for ws, eid in disconnected:
            self.disconnect(ws, eid)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast to all connected clients."""
        message = json.dumps({"type": event_type, **data}, ensure_ascii=False, default=str)
        all_ws: list[WebSocket] = list(self._global_connections)
        for conns in self._connections.values():
            all_ws.extend(conns)
        for ws in all_ws:
            try:
                await ws.send_text(message)
            except Exception:
                pass


ws_manager = WSManager()
