from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class _ClientChannel:
    websocket: WebSocket
    role: str = "telemetry"
    control: deque[dict[str, Any]] = field(default_factory=deque)
    latest_binary: bytes | None = None
    latest_binary_metadata: dict[str, Any] | None = None
    dropped_control: int = 0
    dropped_binary: int = 0
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    sender: asyncio.Task[None] | None = None

    @property
    def pending(self) -> int:
        return len(self.control) + (1 if self.latest_binary is not None else 0)


class EventHub:
    """Distribuye eventos sin permitir que los JPEG formen una cola creciente."""

    def __init__(self) -> None:
        self._clients: dict[str, dict[WebSocket, _ClientChannel]] = defaultdict(dict)
        self._history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._control_queue_limit = 100

    async def add(self, session_id: str, websocket: WebSocket, role: str = "telemetry") -> None:
        channel = _ClientChannel(websocket, role=role)
        channel.sender = asyncio.create_task(self._sender_loop(session_id, channel), name=f"ws-sender-{session_id[:8]}")
        async with self._lock:
            self._clients[session_id][websocket] = channel

    async def remove(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            channel = self._clients.get(session_id, {}).pop(websocket, None)
            if not self._clients.get(session_id):
                self._clients.pop(session_id, None)
        if channel is not None and channel.sender is not asyncio.current_task():
            if channel.sender is not None:
                channel.sender.cancel()
                try:
                    await channel.sender
                except asyncio.CancelledError:
                    pass

    async def _sender_loop(self, session_id: str, channel: _ClientChannel) -> None:
        try:
            while True:
                async with channel.condition:
                    while not channel.control and channel.latest_binary is None:
                        await channel.condition.wait()
                    if channel.control:
                        payload = channel.control.popleft()
                        binary = None
                    else:
                        payload = None
                        binary = channel.latest_binary
                        metadata = channel.latest_binary_metadata
                        channel.latest_binary = None
                        channel.latest_binary_metadata = None
                if binary is None:
                    sent_at = time.time()
                    payload["sentAt"] = sent_at
                    if isinstance(payload.get("data"), dict):
                        payload["data"]["sentAt"] = sent_at
                    await channel.websocket.send_json(payload)
                else:
                    sent_at = time.time()
                    if metadata is not None:
                        metadata["sentAt"] = sent_at
                        metadata.get("data", {})["sentAt"] = sent_at
                    wire = json.dumps(metadata, separators=(",", ":")).encode("utf-8") if metadata is not None else b"{}"
                    await channel.websocket.send_bytes(wire + b"\n" + binary)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Cliente WebSocket desconectado durante el envio", exc_info=True)
            await self.remove(session_id, channel.websocket)

    async def _enqueue_control(self, channel: _ClientChannel, payload: dict[str, Any]) -> None:
        async with channel.condition:
            # Vida/escudo es un stream de estado: conservar solo el último
            # evento evita que el frontend pinte lecturas antiguas.
            if payload.get("type") == "health_shield.updated":
                channel.control = deque(item for item in channel.control if item.get("type") != "health_shield.updated")
            if len(channel.control) >= self._control_queue_limit:
                channel.control.popleft()
                channel.dropped_control += 1
            channel.control.append(payload)
            channel.condition.notify()

    async def _enqueue_binary(self, channel: _ClientChannel, metadata: dict[str, Any], binary: bytes) -> None:
        async with channel.condition:
            if channel.latest_binary is not None:
                channel.dropped_binary += 1
            channel.latest_binary_metadata = metadata
            channel.latest_binary = binary
            channel.condition.notify()

    async def _channels(self, session_id: str, role: str | None = None) -> list[_ClientChannel]:
        async with self._lock:
            channels = list(self._clients.get(session_id, {}).values())
        return [channel for channel in channels if role is None or channel.role == role]

    def metrics(self, session_id: str) -> dict[str, int]:
        channels = list(self._clients.get(session_id, {}).values())
        return {
            "websocketClients": len(channels),
            "websocketPending": sum(channel.pending for channel in channels),
            "websocketDropped": sum(channel.dropped_binary + channel.dropped_control for channel in channels),
            "websocketVisualDropped": sum(channel.dropped_binary for channel in channels),
        }

    async def publish(self, session_id: str, event_type: str, data: dict[str, Any], status: str = "ready", source: str = "backend") -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        common = {"sessionId": session_id, "predictionId": f"pred-{int(datetime.now().timestamp() * 1000)}", "timestamp": timestamp, "source": source, "status": status}
        payload = {"type": event_type, "contractVersion": "1.1", **common, "data": {**common, **data}}
        self._history[session_id].append(payload)
        self._history[session_id] = self._history[session_id][-200:]
        clients = await self._channels(session_id, "telemetry")
        for channel in clients:
            await self._enqueue_control(channel, payload)

    async def publish_binary(self, session_id: str, event_type: str, data: dict[str, Any], binary: bytes, status: str = "ready", source: str = "backend") -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        common = {"sessionId": session_id, "predictionId": f"pred-{int(datetime.now().timestamp() * 1000)}", "timestamp": timestamp, "source": source, "status": status}
        metrics = self.metrics(session_id)
        metadata = {"type": event_type, "contractVersion": "1.1", **common, "data": {**common, **data, "transport": "binary", "imageBytes": len(binary), **metrics}}
        self._history[session_id].append(metadata)
        self._history[session_id] = self._history[session_id][-200:]
        clients = await self._channels(session_id, "visual")
        for channel in clients:
            await self._enqueue_binary(channel, metadata, binary)

    def history(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(session_id, []))
