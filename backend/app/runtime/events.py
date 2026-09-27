from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class EventHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def add(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients[session_id].add(websocket)

    async def remove(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients[session_id].discard(websocket)
            if not self._clients[session_id]:
                self._clients.pop(session_id, None)

    async def publish(self, session_id: str, event_type: str, data: dict[str, Any], status: str = "ready", source: str = "backend") -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        common = {"sessionId": session_id, "predictionId": f"pred-{int(datetime.now().timestamp() * 1000)}", "timestamp": timestamp, "source": source, "status": status}
        payload = {"type": event_type, "contractVersion": "1.1", **common, "data": {**common, **data}}
        self._history[session_id].append(payload)
        self._history[session_id] = self._history[session_id][-200:]
        async with self._lock:
            clients = list(self._clients.get(session_id, set()))
        for websocket in clients:
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 - un cliente perdido no detiene la sesión
                await self.remove(session_id, websocket)

    def history(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(session_id, []))
