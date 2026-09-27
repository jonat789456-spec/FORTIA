from __future__ import annotations

import asyncio
import base64
import io
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from PIL import Image

from ..capture.windows import WindowInfo, capture_window, enumerate_windows
from ..config import settings
from ..inference.service import InferenceService
from ..preprocessing.baseline import crops_feature, sequence_feature
from ..preprocessing.structured import HealthShieldReader, InventoryReader
from ..recommendations import HealthAlertGate, evaluate, evaluate_prediction


Publish = Callable[[str, str, dict[str, object], str], Awaitable[None]]


@dataclass
class PipelineState:
    status: str = "idle"
    frames_captured: int = 0
    frames_dropped: int = 0
    last_timestamp: float | None = None
    window: WindowInfo | None = None


class LatestFrameBuffer:
    """Buffer de capacidad uno: conserva el frame más reciente."""

    def __init__(self) -> None:
        self._value = None
        self.dropped = 0
        self._lock = asyncio.Lock()

    async def put(self, value: object) -> None:
        async with self._lock:
            if self._value is not None:
                self.dropped += 1
            self._value = value

    async def get(self):
        async with self._lock:
            value, self._value = self._value, None
            return value


class RuntimePipeline:
    def __init__(self, publish: Publish, inference: InferenceService | None = None) -> None:
        self.publish = publish
        self.inference = inference or InferenceService()
        self.states: dict[str, PipelineState] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.buffers: dict[str, LatestFrameBuffer] = {}
        self.histories: dict[str, deque[object]] = {}
        self.last_sequence_sample: dict[str, float] = {}
        self.inference_tasks: dict[str, asyncio.Task[None]] = {}
        self.health_readers: dict[str, HealthShieldReader] = {}
        self.inventory_readers: dict[str, InventoryReader] = {}
        self.health_alert_gates: dict[str, HealthAlertGate] = {}

    async def start(self, session_id: str) -> None:
        await self.stop(session_id)
        self.states[session_id] = PipelineState(status="searching")
        self.buffers[session_id] = LatestFrameBuffer()
        self.histories[session_id] = deque(maxlen=6)
        self.last_sequence_sample[session_id] = 0.0
        self.health_readers[session_id] = HealthShieldReader()
        self.inventory_readers[session_id] = InventoryReader()
        self.health_alert_gates[session_id] = HealthAlertGate()
        self.tasks[session_id] = asyncio.create_task(self._capture_loop(session_id), name=f"capture-{session_id}")

    async def stop(self, session_id: str) -> None:
        task = self.tasks.pop(session_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if session_id in self.states:
            self.states[session_id].status = "idle"
        inference_task = self.inference_tasks.pop(session_id, None)
        if inference_task is not None:
            inference_task.cancel()
        self.histories.pop(session_id, None)
        self.last_sequence_sample.pop(session_id, None)
        self.health_readers.pop(session_id, None)
        self.inventory_readers.pop(session_id, None)
        self.health_alert_gates.pop(session_id, None)

    async def _emit_status(self, session_id: str, status: str, message: str) -> None:
        state = self.states.setdefault(session_id, PipelineState())
        state.status = status
        if settings.capture_mode.casefold() == "alternative":
            message = f"Modo de prueba de captura: {message}"
        await self.publish(session_id, "capture.status", {"captureState": status, "captureMode": "alternative" if settings.capture_mode.casefold() == "alternative" else "fortnite", "message": message, "framesCaptured": state.frames_captured, "framesDropped": state.frames_dropped}, status if status in {"error", "unavailable"} else "ready")

    async def _capture_loop(self, session_id: str) -> None:
        interval = 1 / max(1, settings.capture_fps)
        last_status = None
        while True:
            started = time.perf_counter()
            windows = await asyncio.to_thread(enumerate_windows)
            if not windows:
                if last_status != "searching":
                    await self._emit_status(session_id, "searching", "Buscando la ventana de Fortnite.")
                    last_status = "searching"
                await asyncio.sleep(0.5)
                continue
            window = windows[0]
            self.states[session_id].window = window
            if window.minimized:
                if last_status != "minimized":
                    await self._emit_status(session_id, "minimized", "La ventana de Fortnite está minimizada.")
                    last_status = "minimized"
                await asyncio.sleep(0.5)
                continue
            frame = await asyncio.to_thread(capture_window, window)
            if frame is None:
                await self._emit_status(session_id, "lost", "Se perdió temporalmente la captura de Fortnite.")
                last_status = "lost"
                await asyncio.sleep(0.5)
                continue
            await self.buffers[session_id].put(frame)
            current = await self.buffers[session_id].get()
            if current is not None:
                state = self.states[session_id]
                state.status = "capturing"
                state.frames_captured += 1
                state.frames_dropped = self.buffers[session_id].dropped
                state.last_timestamp = time.time()
                encoded = io.BytesIO()
                Image.fromarray(current).save(encoded, format="JPEG", quality=75, optimize=True)
                image_data = base64.b64encode(encoded.getvalue()).decode("ascii")
                is_alternative = settings.capture_mode.casefold() == "alternative"
                await self.publish(session_id, "stream.updated", {"available": True, "image": f"data:image/jpeg;base64,{image_data}", "frameId": state.frames_captured, "resolution": f"{window.width}x{window.height}", "fps": settings.stream_fps, "captureState": "capturing", "framesDropped": state.frames_dropped, "captureMode": "alternative" if is_alternative else "fortnite", "message": "Modo de prueba de captura." if is_alternative else "Captura de Fortnite activa."}, "ready")
                now = time.time()
                if now - self.last_sequence_sample[session_id] >= 1.0:
                    self.last_sequence_sample[session_id] = now
                    self.histories[session_id].append(current.copy())
                    task = self.inference_tasks.get(session_id)
                    if task is None or task.done():
                        self.inference_tasks[session_id] = asyncio.create_task(self._infer_latest(session_id, window), name=f"inference-{session_id}")
            elapsed = time.perf_counter() - started
            await asyncio.sleep(max(0, interval - elapsed))

    @staticmethod
    def _crop(frame, window: WindowInfo, x0: int, x1: int, y0: int, y1: int):
        height, width = frame.shape[:2]
        scale_x, scale_y = width / 1360, height / 768
        left, right = max(0, int(x0 * scale_x)), min(width, int(x1 * scale_x))
        top, bottom = max(0, int(y0 * scale_y)), min(height, int(y1 * scale_y))
        return frame[top:bottom, left:right]

    @staticmethod
    def _image_data_uri(frame, quality: int = 75) -> str:
        image_buffer = io.BytesIO()
        Image.fromarray(frame).save(image_buffer, format="JPEG", quality=quality, optimize=True)
        return f"data:image/jpeg;base64,{base64.b64encode(image_buffer.getvalue()).decode('ascii')}"

    async def _infer_latest(self, session_id: str, window: WindowInfo) -> None:
        history = list(self.histories.get(session_id, []))
        if len(history) < 6:
            return
        frame = history[-1]
        crops = {
            "health": self._crop(frame, window, 0, 489, 552, 768),
            "inventory": self._crop(frame, window, 720, 1360, 583, 768),
            "map": self._crop(frame, window, 1047, 1360, 0, 261),
        }
        predictions: dict[str, dict[str, object]] = {}
        predictions["frames"] = await asyncio.to_thread(self.inference.predict, "frames", sequence_feature(history))
        for modality, crop in crops.items():
            predictions[modality] = await asyncio.to_thread(self.inference.predict, modality, crops_feature([crop]))
        health = self.health_readers[session_id].read(crops["health"])
        health_prediction = predictions["health"]
        gate = self.health_alert_gates.setdefault(session_id, HealthAlertGate())
        health_alerts = gate.update(health.get("healthValue"), health.get("shieldValue"), float(health.get("confidence", 0.0)), str(health.get("status", "not_detected")), float(health.get("healthConfidence", 0.0)), float(health.get("shieldConfidence", 0.0)), health_state=health.get("healthReading"), shield_state=health.get("shieldReading"))
        health_payload = {**health, "modelVersion": health_prediction.get("modelVersion"), "health": health.get("healthValue"), "shield": health.get("shieldValue"), "trend": [], "healthAlertActive": gate.health_active, "shieldAlertActive": gate.shield_active}
        if health_prediction.get("status") == "ready":
            health_payload.update({"winProbability": health_prediction["binary"]["winProbability"], "lossProbability": health_prediction["binary"]["lossProbability"], "classProbabilities": health_prediction["classProbabilities"], "predictionConfidence": health_prediction["confidence"], "latencyMs": health_prediction["latencyMs"]})
        await self.publish(session_id, "health_shield.updated", health_payload, health["status"])
        inventory = self.inventory_readers[session_id].read(crops["inventory"])
        inventory_prediction = predictions["inventory"]
        inventory_payload = {**inventory, "modelVersion": inventory_prediction.get("modelVersion")}
        inventory_items = []
        inventory_crop = crops["inventory"]
        slot_width = max(1, inventory_crop.shape[1] // 5)
        for index, slot in enumerate(inventory.get("slots", [])):
            left = index * slot_width
            right = inventory_crop.shape[1] if index == 4 else min(inventory_crop.shape[1], (index + 1) * slot_width)
            inventory_items.append({"id": f"slot-{index + 1}", "position": slot["position"], "occupied": slot["occupied"], "name": slot.get("name") or "Objeto no identificado", "category": slot.get("category"), "rarity": slot.get("rarity") or "No disponible", "quantity": slot.get("quantity") or 0, "ammo": slot.get("ammo"), "confidence": slot.get("confidence", 0.0), "icon": self._image_data_uri(inventory_crop[:, left:right])})
        inventory_payload["items"] = inventory_items
        if inventory_prediction.get("status") == "ready":
            inventory_payload.update({"winProbability": inventory_prediction["binary"]["winProbability"], "lossProbability": inventory_prediction["binary"]["lossProbability"], "classProbabilities": inventory_prediction["classProbabilities"], "predictionConfidence": inventory_prediction["confidence"], "latencyMs": inventory_prediction["latencyMs"]})
        await self.publish(session_id, "inventory.updated", inventory_payload, inventory["status"])
        await self.publish(session_id, "audio_prediction.updated", {"status": "unavailable", "reason": "El dataset contiene espectrogramas PNG, pero aún no hay captura de audio crudo conectada al pipeline.", "modelVersion": self.inference.versions.get("audio")}, "unavailable")
        for modality in ("map", "sequence"):
            model_name = "frames" if modality == "sequence" else modality
            prediction = predictions[model_name]
            if prediction.get("status") != "ready":
                continue
            payload = {"winProbability": prediction["binary"]["winProbability"], "lossProbability": prediction["binary"]["lossProbability"], "classProbabilities": prediction["classProbabilities"], "confidence": prediction["confidence"], "latencyMs": prediction["latencyMs"], "modelVersion": prediction["modelVersion"]}
            if modality == "map":
                payload["image"] = self._image_data_uri(crops["map"])
                await self.publish(session_id, "map.updated", payload, "ready")
            else:
                payload["frames"] = [{"id": f"frame-{index}", "index": index, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "ready", "image": self._image_data_uri(value)} for index, value in enumerate(history[-6:], start=1)]
                await self.publish(session_id, "frame_sequence.updated", payload, "ready")
        fusion = self.inference.fuse(predictions)
        if fusion.get("status") == "ready":
            probabilities = fusion["classProbabilities"]
            await self.publish(session_id, "main_prediction.updated", {"predictedClass": {"Eliminado": "eliminated", "Eliminacion": "elimination", "Victoria": "victory"}[fusion["predictedClass"]], "eliminatedProbability": probabilities["Eliminado"], "eliminationProbability": probabilities["Eliminacion"], "victoryProbability": probabilities["Victoria"], "confidence": fusion["confidence"], "latencyMs": 0, "modelVersion": fusion["modelVersion"], "participatingModalities": fusion["participatingModalities"], "missingModalities": fusion["missingModalities"]}, "ready")
            recommendations = evaluate(session_id, health.get("healthValue"), health.get("shieldValue"), enabled_alerts=health_alerts) + evaluate_prediction(session_id, float(probabilities["Eliminado"]), list(fusion["missingModalities"]))
            for recommendation in recommendations:
                await self.publish(session_id, "recommendation.updated", recommendation, "ready")
