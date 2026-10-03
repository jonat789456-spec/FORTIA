from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

from PIL import Image

from ..audio.capture import AudioConfig, LoopbackAudioCapture
from ..audio.model import waveform_quality
from ..capture.windows import WindowInfo, capture_window, enumerate_windows
from ..config import settings
from ..inference.service import InferenceService
from ..preprocessing.baseline import crops_feature, sequence_feature
from ..preprocessing.structured import HealthShieldReader, InventoryReader
from ..recommendations import HealthAlertGate, evaluate, evaluate_prediction
from ..collection.failure_recorder import FailureRecorder
from ..inference.risk import TemporalRiskFeatures, RiskSmoother, point_from_payload
from ..class_mapping import frontend_class_from_name

logger = logging.getLogger(__name__)

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - dependencia opcional en entornos mínimos
    psutil = None


Publish = Callable[[str, str, dict[str, object], str], Awaitable[None]]
BinaryPublish = Callable[[str, str, dict[str, object], bytes, str], Awaitable[None]]


@dataclass
class PipelineState:
    status: str = "idle"
    frames_captured: int = 0
    frames_dropped: int = 0
    health_frames_dropped: int = 0
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
    def __init__(self, publish: Publish, inference: InferenceService | None = None, publish_binary: BinaryPublish | None = None) -> None:
        self.publish = publish
        self.publish_binary = publish_binary
        self.inference = inference or InferenceService()
        self.states: dict[str, PipelineState] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.capture_executors: dict[str, ThreadPoolExecutor] = {}
        self.stream_encode_executors: dict[str, ThreadPoolExecutor] = {}
        self.stream_tasks: dict[str, asyncio.Task[None]] = {}
        self.buffers: dict[str, LatestFrameBuffer] = {}
        self.latest_frames: dict[str, tuple[object, WindowInfo, int, float, float] | None] = {}
        self.capture_times: dict[str, deque[float]] = {}
        self.stream_times: dict[str, deque[float]] = {}
        self.stream_last_log: dict[str, float] = {}
        self.adaptive_stream_fps: dict[str, float] = {}
        self.adaptive_stream_quality: dict[str, int] = {}
        self.adaptive_stream_width: dict[str, int] = {}
        self.adaptive_last_adjust: dict[str, float] = {}
        self.histories: dict[str, deque[object]] = {}
        self.last_sequence_sample: dict[str, float] = {}
        self.inference_tasks: dict[str, asyncio.Task[None]] = {}
        self.health_readers: dict[str, HealthShieldReader] = {}
        self.inventory_readers: dict[str, InventoryReader] = {}
        self.inventory_last_valid: dict[str, tuple[str, float]] = {}
        self.inventory_last_log: dict[str, float] = {}
        self.health_alert_gates: dict[str, HealthAlertGate] = {}
        self.health_tasks: dict[str, asyncio.Task[None]] = {}
        self.health_payloads: dict[str, dict[str, object]] = {}
        self.last_health_sample: dict[str, float] = {}
        self.web_last_ingest: dict[str, float] = {}
        self.health_pending: dict[str, tuple[object, WindowInfo, float] | None] = {}
        self.health_sequence: dict[str, int] = {}
        self.health_times: dict[str, deque[float]] = {}
        self.audio_tasks: dict[str, asyncio.Task[None]] = {}
        self.audio_captures: dict[str, LoopbackAudioCapture] = {}
        self.audio_payloads: dict[str, dict[str, object]] = {}
        self.audio_suppressed: dict[str, bool] = {}
        self.risk_features: dict[str, TemporalRiskFeatures] = {}
        self.risk_smoothers: dict[str, RiskSmoother] = {}
        self.failure_recorder = FailureRecorder(settings.failure_collection_root, settings.failure_collection_enabled, settings.failure_collection_max_cases)

    def set_audio_suppressed(self, session_id: str, suppressed: bool) -> None:
        self.audio_suppressed[session_id] = suppressed

    async def record_outcome(self, session_id: str, outcome: dict[str, object]) -> dict[str, object]:
        """Registra explícitamente un resultado real cuando la recolección está activa."""
        history = list(self.histories.get(session_id, []))[-6:]
        frames: list[bytes] = []
        for frame in history:
            buffer = io.BytesIO()
            Image.fromarray(frame).save(buffer, format="JPEG", quality=82, optimize=True)
            frames.append(buffer.getvalue())
        case = {"sessionId": session_id, **outcome}
        stored = await asyncio.to_thread(self.failure_recorder.record_case, case, frames)
        return {"stored": stored, "enabled": self.failure_recorder.enabled, "sessionId": session_id}

    async def start(self, session_id: str) -> None:
        await self.stop(session_id)
        self.states[session_id] = PipelineState(status="searching")
        self.buffers[session_id] = LatestFrameBuffer()
        self.capture_executors[session_id] = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"capture-{session_id[:8]}")
        self.stream_encode_executors[session_id] = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"stream-encode-{session_id[:8]}")
        self.latest_frames[session_id] = None
        self.capture_times[session_id] = deque(maxlen=90)
        self.stream_times[session_id] = deque(maxlen=90)
        self.stream_last_log[session_id] = 0.0
        self.adaptive_stream_fps[session_id] = float(settings.stream_fps)
        self.adaptive_stream_quality[session_id] = settings.stream_jpeg_quality
        self.adaptive_stream_width[session_id] = settings.stream_max_width
        self.adaptive_last_adjust[session_id] = 0.0
        self.histories[session_id] = deque(maxlen=6)
        self.last_sequence_sample[session_id] = 0.0
        self.health_readers[session_id] = HealthShieldReader()
        self.inventory_readers[session_id] = InventoryReader()
        self.health_alert_gates[session_id] = HealthAlertGate()
        self.last_health_sample[session_id] = 0.0
        self.web_last_ingest[session_id] = 0.0
        self.health_payloads.pop(session_id, None)
        self.health_pending[session_id] = None
        self.health_sequence[session_id] = 0
        self.health_times[session_id] = deque(maxlen=120)
        self.risk_features[session_id] = TemporalRiskFeatures()
        self.risk_smoothers[session_id] = RiskSmoother()
        if settings.capture_mode.casefold() != "web":
            self.tasks[session_id] = asyncio.create_task(self._capture_loop(session_id), name=f"capture-{session_id}")
        self.stream_tasks[session_id] = asyncio.create_task(self._stream_loop(session_id), name=f"stream-{session_id}")
        self.audio_tasks[session_id] = asyncio.create_task(self._audio_loop(session_id), name=f"audio-{session_id}")

    async def stop(self, session_id: str) -> None:
        task = self.tasks.pop(session_id, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        stream_task = self.stream_tasks.pop(session_id, None)
        if stream_task is not None:
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
        capture_executor = self.capture_executors.pop(session_id, None)
        if capture_executor is not None:
            capture_executor.shutdown(wait=False, cancel_futures=True)
        stream_encode_executor = self.stream_encode_executors.pop(session_id, None)
        if stream_encode_executor is not None:
            stream_encode_executor.shutdown(wait=False, cancel_futures=True)
        if session_id in self.states:
            self.states[session_id].status = "idle"
        inference_task = self.inference_tasks.pop(session_id, None)
        if inference_task is not None:
            inference_task.cancel()
        health_task = self.health_tasks.pop(session_id, None)
        if health_task is not None:
            health_task.cancel()
        audio_task = self.audio_tasks.pop(session_id, None)
        if audio_task is not None:
            audio_task.cancel()
            try:
                await audio_task
            except asyncio.CancelledError:
                pass
        capture = self.audio_captures.pop(session_id, None)
        if capture is not None:
            capture.close()
        self.audio_payloads.pop(session_id, None)
        self.audio_suppressed.pop(session_id, None)
        self.risk_features.pop(session_id, None)
        self.risk_smoothers.pop(session_id, None)
        self.histories.pop(session_id, None)
        self.latest_frames.pop(session_id, None)
        self.capture_times.pop(session_id, None)
        self.stream_times.pop(session_id, None)
        self.stream_last_log.pop(session_id, None)
        self.adaptive_stream_fps.pop(session_id, None)
        self.adaptive_stream_quality.pop(session_id, None)
        self.adaptive_stream_width.pop(session_id, None)
        self.adaptive_last_adjust.pop(session_id, None)
        self.last_sequence_sample.pop(session_id, None)
        self.health_readers.pop(session_id, None)
        self.inventory_readers.pop(session_id, None)
        self.inventory_last_valid.pop(session_id, None)
        self.inventory_last_log.pop(session_id, None)
        self.health_alert_gates.pop(session_id, None)
        self.health_payloads.pop(session_id, None)
        self.health_pending.pop(session_id, None)
        self.health_sequence.pop(session_id, None)
        self.health_times.pop(session_id, None)
        self.last_health_sample.pop(session_id, None)
        self.web_last_ingest.pop(session_id, None)

    async def ingest_web_frame(self, session_id: str, frame) -> dict[str, object]:
        """Acepta el último frame autorizado por el navegador.

        El buffer es de capacidad uno: si el backend va retrasado, el frame
        anterior se descarta y no se acumula trabajo ni memoria.
        """
        if session_id not in self.states or session_id not in self.latest_frames:
            raise KeyError(session_id)
        height, width = frame.shape[:2]
        if width <= 0 or height <= 0:
            raise ValueError("Frame vacío")
        window = WindowInfo(0, "Captura autorizada del navegador", 0, 0, width, height, False)
        now = time.time()
        state = self.states[session_id]
        state.status = "capturing"
        state.frames_captured += 1
        state.last_timestamp = now
        self.capture_times[session_id].append(now)
        capture_ms = 0.0
        if self.latest_frames[session_id] is not None:
            state.frames_dropped += 1
        self.latest_frames[session_id] = (frame, window, state.frames_captured, now, capture_ms)
        health_interval = 1 / max(1, settings.health_fast_fps)
        if now - self.last_health_sample[session_id] >= health_interval:
            self.last_health_sample[session_id] = now
            health_task = self.health_tasks.get(session_id)
            if health_task is None or health_task.done():
                self.health_tasks[session_id] = asyncio.create_task(self._health_fast(session_id, frame.copy(), window, now), name=f"health-fast-{session_id}")
            else:
                self.health_pending[session_id] = (frame.copy(), window, now)
                state.health_frames_dropped += 1
        if now - self.last_sequence_sample[session_id] >= max(0.25, settings.health_verification_interval_sec):
            self.last_sequence_sample[session_id] = now
            self.histories[session_id].append(frame.copy())
            task = self.inference_tasks.get(session_id)
            if task is None or task.done():
                self.inference_tasks[session_id] = asyncio.create_task(self._infer_latest(session_id, window), name=f"inference-{session_id}")
        return {"accepted": True, "frameId": state.frames_captured, "framesDropped": state.frames_dropped, "fps": round(self._observed_fps(self.capture_times[session_id]), 1)}

    async def _emit_status(self, session_id: str, status: str, message: str) -> None:
        state = self.states.setdefault(session_id, PipelineState())
        state.status = status
        if settings.capture_mode.casefold() == "alternative":
            message = f"Modo de prueba de captura: {message}"
        await self.publish(session_id, "capture.status", {"captureState": status, "captureMode": "alternative" if settings.capture_mode.casefold() == "alternative" else "fortnite", "message": message, "framesCaptured": state.frames_captured, "framesDropped": state.frames_dropped}, status if status in {"error", "unavailable"} else "ready")

    @staticmethod
    def _observed_fps(times: deque[float]) -> float:
        if len(times) < 2:
            return 0.0
        elapsed = times[-1] - times[0]
        return (len(times) - 1) / elapsed if elapsed > 0 else 0.0

    @staticmethod
    def _resource_metrics() -> dict[str, float]:
        if psutil is None:
            return {}
        try:
            process = psutil.Process()
            metrics = {"cpuPercent": round(process.cpu_percent(None), 1), "memoryMb": round(process.memory_info().rss / (1024 * 1024), 1)}
            try:
                import torch  # type: ignore

                if torch.cuda.is_available():
                    metrics["gpuMemoryMb"] = round(torch.cuda.memory_allocated() / (1024 * 1024), 1)
            except (ImportError, OSError, RuntimeError):
                pass
            return metrics
        except (OSError, RuntimeError):
            return {}

    async def _stream_loop(self, session_id: str) -> None:
        while True:
            started = time.perf_counter()
            item = self.latest_frames.get(session_id)
            if item is not None:
                frame, window, frame_id, captured_at, capture_ms = item
                self.latest_frames[session_id] = None
                encode_started = time.perf_counter()
                loop = asyncio.get_running_loop()
                image_bytes_raw, encoded_width, encoded_height, image_bytes, resize_ms, encode_ms = await loop.run_in_executor(self.stream_encode_executors[session_id], self._encode_stream_frame, frame, self.adaptive_stream_quality[session_id], self.adaptive_stream_width[session_id])
                encoded_at = time.time()
                stream_times = self.stream_times[session_id]
                stream_times.append(encoded_at)
                stream_fps = self._observed_fps(stream_times)
                state = self.states[session_id]
                send_started = time.perf_counter()
                stream_data = {"available": True, "frameId": frame_id, "sequence": frame_id, "resolution": f"{encoded_width}x{encoded_height}", "fps": round(stream_fps, 1), "captureFps": round(self._observed_fps(self.capture_times[session_id]), 1), "encodedFps": round(stream_fps, 1), "streamFps": round(stream_fps, 1), "captureMs": round(capture_ms, 3), "resizeMs": round(resize_ms, 3), "encodeMs": round(encode_ms, 3), "imageBytes": image_bytes, "capturedAt": captured_at, "captureTimestamp": captured_at, "encodedAt": encoded_at, "encodedTimestamp": encoded_at, "latencyMs": round((time.time() - captured_at) * 1000, 3), "resolutionSource": f"{window.width}x{window.height}", "captureState": "capturing", "framesDropped": state.frames_dropped, "captureMode": "alternative" if settings.capture_mode.casefold() == "alternative" else "fortnite", "message": "Modo de prueba de captura." if settings.capture_mode.casefold() == "alternative" else "Captura de Fortnite activa.", **self._resource_metrics()}
                if self.publish_binary is not None:
                    await self.publish_binary(session_id, "stream.updated", stream_data, image_bytes_raw, "ready")
                else:
                    stream_data["image"] = f"data:image/jpeg;base64,{base64.b64encode(image_bytes_raw).decode('ascii')}"
                    await self.publish(session_id, "stream.updated", stream_data, "ready")
                send_ms = (time.perf_counter() - send_started) * 1000
                self._adapt_stream(session_id, capture_ms, resize_ms, encode_ms, send_ms, stream_fps)
                logger.debug("stream enqueue: frame=%s ms=%.3f", frame_id, send_ms)
                now = time.time()
                if now - self.stream_last_log[session_id] >= 2.0:
                    logger.info("stream metrics: capture_fps=%.1f stream_fps=%.1f source=%sx%s encoded=%sx%s image_bytes=%d resize_ms=%.2f encode_ms=%.2f send_ms=%.2f latency_ms=%.2f dropped=%d", self._observed_fps(self.capture_times[session_id]), stream_fps, window.width, window.height, encoded_width, encoded_height, image_bytes, resize_ms, encode_ms, time.perf_counter() - send_started, (time.time() - captured_at) * 1000, state.frames_dropped)
                    self.stream_last_log[session_id] = now
            interval = 1 / max(1, self.adaptive_stream_fps.get(session_id, float(settings.stream_fps)))
            await asyncio.sleep(max(0.0, interval - (time.perf_counter() - started)))

    def _adapt_stream(self, session_id: str, capture_ms: float, resize_ms: float, encode_ms: float, send_ms: float, stream_fps: float) -> None:
        if not settings.stream_adaptive:
            return
        now = time.monotonic()
        if now - self.adaptive_last_adjust.get(session_id, 0.0) < 1.0:
            return
        pressure = capture_ms + resize_ms + encode_ms + send_ms > (1000 / max(1, settings.stream_fps)) * 0.85
        resource = self._resource_metrics()
        pressure = pressure or resource.get("cpuPercent", 0.0) >= 85.0 or (stream_fps > 0 and stream_fps < settings.stream_min_fps)
        current_fps = self.adaptive_stream_fps.get(session_id, float(settings.stream_fps))
        current_quality = self.adaptive_stream_quality.get(session_id, settings.stream_jpeg_quality)
        if pressure:
            self.adaptive_stream_quality[session_id] = max(55, current_quality - 5)
            if current_quality <= 60:
                self.adaptive_stream_width[session_id] = min(self.adaptive_stream_width[session_id], settings.stream_fallback_width)
            if current_quality <= 55:
                self.adaptive_stream_fps[session_id] = max(float(settings.stream_min_fps), current_fps - 1)
            self.adaptive_last_adjust[session_id] = now
            logger.warning("stream adaptive: pressure=true fps=%.0f quality=%d", self.adaptive_stream_fps[session_id], self.adaptive_stream_quality[session_id])
        elif current_fps < settings.stream_fps or current_quality < settings.stream_jpeg_quality:
            self.adaptive_stream_fps[session_id] = min(float(settings.stream_fps), current_fps + 1)
            self.adaptive_stream_quality[session_id] = min(settings.stream_jpeg_quality, current_quality + 2)
            self.adaptive_last_adjust[session_id] = now

    @staticmethod
    def _encode_stream_frame(frame, quality_override: int | None = None, width_override: int | None = None) -> tuple[bytes, int, int, int, float, float]:
        resize_started = time.perf_counter()
        image = Image.fromarray(frame)
        width = min(image.width, settings.stream_max_width if width_override is None else width_override)
        if image.width > width:
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        resize_ms = (time.perf_counter() - resize_started) * 1000
        total_encode_ms = 0.0
        raw = b""
        while True:
            target_quality = settings.stream_jpeg_quality if quality_override is None else quality_override
            for quality in range(max(40, min(95, target_quality)), 39, -5):
                encode_started = time.perf_counter()
                encoded = io.BytesIO()
                image.save(encoded, format="JPEG", quality=quality, optimize=False)
                raw = encoded.getvalue()
                total_encode_ms += (time.perf_counter() - encode_started) * 1000
                if len(raw) <= settings.stream_max_bytes or quality == 40:
                    break
            if len(raw) <= settings.stream_max_bytes or image.width <= 640:
                break
            next_width = max(640, int(image.width * 0.85))
            resize_started = time.perf_counter()
            image = image.resize((next_width, max(1, round(image.height * next_width / image.width))), Image.Resampling.BILINEAR)
            resize_ms += (time.perf_counter() - resize_started) * 1000
        return raw, image.width, image.height, len(raw), resize_ms, total_encode_ms

    async def _capture_loop(self, session_id: str) -> None:
        interval = 1 / max(1, settings.capture_fps)
        last_status = None
        window: WindowInfo | None = None
        next_window_scan = 0.0
        while True:
            started = time.perf_counter()
            now_monotonic = time.monotonic()
            if window is None or now_monotonic >= next_window_scan:
                windows = await asyncio.to_thread(enumerate_windows)
                next_window_scan = now_monotonic + 1.0
                window = windows[0] if windows else None
            if window is None:
                if last_status != "searching":
                    await self._emit_status(session_id, "searching", "Buscando la ventana de Fortnite.")
                    last_status = "searching"
                await asyncio.sleep(0.2)
                continue
            self.states[session_id].window = window
            if window.minimized:
                if last_status != "minimized":
                    await self._emit_status(session_id, "minimized", "La ventana de Fortnite está minimizada.")
                    last_status = "minimized"
                await asyncio.sleep(0.2)
                continue
            loop = asyncio.get_running_loop()
            frame = await loop.run_in_executor(self.capture_executors[session_id], capture_window, window)
            if frame is None:
                await self._emit_status(session_id, "lost", "Se perdió temporalmente la captura de Fortnite.")
                last_status = "lost"
                window = None
                await asyncio.sleep(0.2)
                continue
            current = frame
            if current is not None:
                state = self.states[session_id]
                state.status = "capturing"
                state.frames_captured += 1
                captured_at = time.time()
                state.last_timestamp = captured_at
                self.capture_times[session_id].append(captured_at)
                capture_ms = (time.perf_counter() - started) * 1000
                if self.latest_frames[session_id] is not None:
                    state.frames_dropped += 1
                self.latest_frames[session_id] = (current, window, state.frames_captured, captured_at, capture_ms)
                health_interval = 1 / max(1, settings.health_fast_fps)
                if captured_at - self.last_health_sample[session_id] >= health_interval:
                    self.last_health_sample[session_id] = captured_at
                    health_task = self.health_tasks.get(session_id)
                    if health_task is None or health_task.done():
                        self.health_tasks[session_id] = asyncio.create_task(self._health_fast(session_id, current.copy(), window, captured_at), name=f"health-fast-{session_id}")
                    else:
                        self.health_pending[session_id] = (current.copy(), window, captured_at)
                        state.health_frames_dropped += 1
                now = captured_at
                if now - self.last_sequence_sample[session_id] >= max(0.25, settings.health_verification_interval_sec):
                    self.last_sequence_sample[session_id] = now
                    self.histories[session_id].append(current.copy())
                    task = self.inference_tasks.get(session_id)
                    if task is None or task.done():
                        self.inference_tasks[session_id] = asyncio.create_task(self._infer_latest(session_id, window), name=f"inference-{session_id}")
            elapsed = time.perf_counter() - started
            await asyncio.sleep(max(0, interval - elapsed))

    async def _health_fast(self, session_id: str, frame, window: WindowInfo, captured_at: float) -> None:
        while True:
            started = time.perf_counter()
            crop_started = time.perf_counter()
            crop = self._crop(frame, window, 0, 489, 552, 768)
            crop_ms = (time.perf_counter() - crop_started) * 1000
            reader = self.health_readers.get(session_id)
            if reader is None:
                return
            read_started = time.perf_counter()
            health = await asyncio.to_thread(reader.read, crop, captured_at)
            read_ms = (time.perf_counter() - read_started) * 1000
            gate_started = time.perf_counter()
            gate = self.health_alert_gates.setdefault(session_id, HealthAlertGate())
            enabled = gate.update(health.get("healthValue"), health.get("shieldValue"), float(health.get("confidence", 0.0)), str(health.get("status", "not_detected")), float(health.get("healthConfidence", 0.0)), float(health.get("shieldConfidence", 0.0)), health_state=health.get("healthReading"), shield_state=health.get("shieldReading"))
            validation_ms = (time.perf_counter() - gate_started) * 1000
            processed_at = time.time()
            self.health_sequence[session_id] = self.health_sequence.get(session_id, 0) + 1
            self.health_times.setdefault(session_id, deque(maxlen=120)).append(processed_at)
            times = self.health_times[session_id]
            hz = (len(times) - 1) / max(times[-1] - times[0], 1e-6) if len(times) > 1 else 0.0
            payload = {**health, "sequence": self.health_sequence[session_id], "processingMs": round((time.perf_counter() - started) * 1000, 3), "cropMs": round(crop_ms, 3), "readMs": round(read_ms, 3), "validationMs": round(validation_ms, 3), "capturedAt": captured_at, "inferenceAt": processed_at, "processedAt": processed_at, "actualHz": round(hz, 2), "healthAlertActive": gate.health_active, "shieldAlertActive": gate.shield_active, "healthFramesDropped": self.states[session_id].health_frames_dropped}
            self.health_payloads[session_id] = payload
            tracker = self.risk_features.get(session_id)
            if tracker is not None:
                tracker.add(point_from_payload(payload, captured_at))
            await self.publish(session_id, "health_shield.updated", payload, health["status"])
            if enabled:
                for recommendation in evaluate(session_id, health.get("healthValue"), health.get("shieldValue"), enabled_alerts=enabled):
                    await self.publish(session_id, "recommendation.updated", recommendation, "ready")
            pending = self.health_pending.get(session_id)
            self.health_pending[session_id] = None
            if pending is None:
                return
            frame, window, captured_at = pending

    async def _audio_loop(self, session_id: str) -> None:
        config = AudioConfig(duration_sec=settings.audio_window_sec, hop_sec=settings.audio_hop_sec)
        capture = LoopbackAudioCapture(config, settings.audio_output_device or None)
        self.audio_captures[session_id] = capture
        last_status = None
        last_log = 0.0
        retry_delay = 1.0
        try:
            await self.publish(session_id, "audio_prediction.updated", {"status": "initializing", "source": "wasapi_loopback", "microphone": False, "modelLoaded": self.inference.raw_audio_model is not None, "reason": "Inicializando captura WASAPI."}, "initializing")
            if self.inference.raw_audio_model is None:
                await self.publish(session_id, "audio_prediction.updated", {"status": "model_missing", "source": "wasapi_loopback", "microphone": False, "modelLoaded": False, "reason": "Modelo de audio no encontrado. Ejecuta: python tools/train_audio_raw.py"}, "model_missing")
                return
            while True:
                captured_at = time.time()
                try:
                    if capture.microphone is None:
                        await self.publish(session_id, "audio_prediction.updated", {"status": "device_search", "source": "wasapi_loopback", "microphone": False, "modelLoaded": True, "reason": "Buscando dispositivo de audio…"}, "device_search")
                    waveform = await asyncio.to_thread(capture.read)
                    quality = waveform_quality(waveform)
                    # Se transmite una forma de onda reducida únicamente para
                    # visualización; sus valores provienen del bloque capturado.
                    waveform_preview = waveform[::max(1, waveform.size // 96)].astype(float).tolist()[:96]
                    if self.audio_suppressed.get(session_id, False):
                        await self.publish(session_id, "audio_prediction.updated", {"status": "capturing", "source": "wasapi_loopback", "device": capture.device_name, "deviceName": capture.device_name, "deviceId": capture.device_id, "nativeSampleRate": capture.native_sample_rate, "channels": capture.channels, "modelLoaded": True, "bufferReady": True, "ttsSuppressed": True, "level": quality.get("level", 0.0), "rms": quality.get("rms", 0.0), "peak": quality.get("peak", 0.0), "dbfs": quality.get("dbfs", -60.0), "silence": bool(quality.get("silence")), "waveform": waveform_preview, "reason": "Ventana excluida mientras FORTIA reproduce voz."}, "capturing")
                        await asyncio.sleep(max(0.25, config.hop_sec))
                        continue
                    await self.publish(session_id, "audio_prediction.updated", {"status": "inference", "source": "wasapi_loopback", "device": capture.device_name, "deviceName": capture.device_name, "deviceId": capture.device_id, "nativeSampleRate": capture.native_sample_rate, "channels": capture.channels, "modelLoaded": True, "bufferReady": True, "level": quality.get("level", 0.0), "rms": quality.get("rms", 0.0), "peak": quality.get("peak", 0.0), "dbfs": quality.get("dbfs", -60.0), "silence": bool(quality.get("silence")), "waveform": waveform_preview}, "inference")
                    result = await asyncio.to_thread(self.inference.predict_audio_waveform, waveform, quality)
                    status = "available" if result.get("status") == "ready" else str(result.get("status", "error"))
                    result_status = "ready" if status == "available" else status
                    result.update({"status": result_status, "availabilityStatus": status, "capturedAt": captured_at, "inferenceAt": time.time(), "ageMs": 0.0, "windowSec": config.duration_sec, "hopSec": config.hop_sec, "device": capture.device_name, "deviceName": capture.device_name, "deviceId": capture.device_id, "channels": capture.channels, "nativeSampleRate": capture.native_sample_rate, "modelLoaded": True, "bufferReady": True, "source": "wasapi_loopback", "level": quality.get("level", 0.0), "rms": quality.get("rms", 0.0), "peak": quality.get("peak", 0.0), "dbfs": quality.get("dbfs", -60.0), "silence": bool(quality.get("silence")), "waveform": waveform_preview})
                    self.audio_payloads[session_id] = result
                    await self.publish(session_id, "audio_prediction.updated", result, status if status in {"available", "silence", "low_confidence", "model_missing", "unavailable", "error"} else "error")
                    last_status = status
                    retry_delay = 1.0
                    if time.time() - last_log >= 1.0:
                        logger.info("audio window valid: device=%s blocks=%s samples=%d native_hz=%s rms=%.6f peak=%.6f silence=%s status=%s inference_ms=%.2f", capture.device_name, capture.blocks_received, waveform.size, capture.native_sample_rate, quality["rms"], quality["peak"], quality["silence"], status, result.get("latencyMs", 0.0))
                        logger.info("audio WebSocket event sent: status=%s level=%.2f rms=%.6f peak=%.6f", status, float(quality.get("level", 0.0)), float(quality.get("rms", 0.0)), float(quality.get("peak", 0.0)))
                        last_log = time.time()
                except (RuntimeError, OSError, ValueError) as exc:
                    status = "device_unavailable"
                    capture.close()
                    if last_status != status:
                        payload = {"status": status, "source": "wasapi_loopback", "microphone": False, "modelLoaded": True, "reason": f"Error técnico de captura; reintentando: {exc}", "device": capture.device_name, "deviceId": capture.device_id, "silence": False, "level": 0.0, "rms": 0.0, "peak": 0.0, "bufferReady": False, "modelVersion": self.inference.versions.get("audio_raw")}
                        self.audio_payloads[session_id] = payload
                        await self.publish(session_id, "audio_prediction.updated", payload, status)
                        last_status = status
                    await asyncio.sleep(min(10.0, retry_delay))
                    retry_delay = min(10.0, retry_delay * 2.0)
                    continue
                await asyncio.sleep(max(0.25, config.hop_sec))
        finally:
            capture.close()

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
        sequence_features = await asyncio.to_thread(sequence_feature, history)
        predictions["frames"] = await asyncio.to_thread(self.inference.predict, "frames", sequence_features)
        for modality, crop in crops.items():
            features = await asyncio.to_thread(crops_feature, [crop])
            predictions[modality] = await asyncio.to_thread(self.inference.predict, modality, features)
        inventory = await asyncio.to_thread(self.inventory_readers[session_id].read, crops["inventory"])
        health_payload = self.health_payloads.get(session_id, {})
        risk_tracker = self.risk_features.get(session_id)
        risk_features = risk_tracker.features() if risk_tracker else {}
        risk_shadow = await asyncio.to_thread(self.inference.predict_risk_shadow, risk_features)
        safety = self.inference.safety_signal(risk_features)
        risk_value = risk_shadow.get("riskProbability") if risk_shadow.get("status") == "ready" else None
        smoothed_risk = self.risk_smoothers[session_id].update(risk_value, bool(safety.get("active"))) if session_id in self.risk_smoothers else risk_value
        inventory_prediction = predictions["inventory"]
        inventory_crop = crops["inventory"]
        if inventory_crop.ndim != 3 or inventory_crop.shape[0] <= 0 or inventory_crop.shape[1] <= 0:
            logger.error("ROI de inventario inválido: frame_shape=%s roi_shape=%s window=%s", getattr(frame, "shape", None), getattr(inventory_crop, "shape", None), window)
            current_inventory_image = None
        else:
            current_inventory_image = await asyncio.to_thread(self._image_data_uri, inventory_crop, 82)
            now_log = time.time()
            if now_log - self.inventory_last_log.get(session_id, 0.0) >= 2.0:
                logger.info("ROI de inventario válido: frame_shape=%s roi_shape=%s bytes_jpeg_aprox=%s", frame.shape, inventory_crop.shape, len(current_inventory_image))
                self.inventory_last_log[session_id] = now_log
        inventory_image: str | None = current_inventory_image
        image_is_stale = False
        image_captured_at = time.time()
        if current_inventory_image and inventory.get("status") in {"ready", "available"}:
            self.inventory_last_valid[session_id] = (current_inventory_image, image_captured_at)
        elif session_id in self.inventory_last_valid:
            cached_image, cached_at = self.inventory_last_valid[session_id]
            if image_captured_at - cached_at <= 5.0:
                inventory_image = cached_image
                image_captured_at = cached_at
                image_is_stale = True
        else:
            inventory_image = None
        inventory_payload = {**inventory, "modelVersion": inventory_prediction.get("modelVersion"), "image": inventory_image, "inventoryImage": inventory_image, "imageCapturedAt": image_captured_at, "imageIsStale": image_is_stale, "imageAgeMs": round(max(0.0, time.time() - image_captured_at) * 1000)}
        inventory_items = []
        for index, slot in enumerate(inventory.get("slots", [])):
            inventory_items.append({"id": f"slot-{index + 1}", "position": slot["position"], "occupied": slot["occupied"], "name": slot.get("name") or "Objeto no identificado", "category": slot.get("category"), "rarity": slot.get("rarity") or "No disponible", "quantity": slot.get("quantity") or 0, "ammo": slot.get("ammo"), "confidence": slot.get("confidence", 0.0)})
        inventory_payload["items"] = inventory_items
        if inventory_prediction.get("status") == "ready":
            inventory_payload.update({"winProbability": inventory_prediction["binary"]["winProbability"], "lossProbability": inventory_prediction["binary"]["lossProbability"], "classProbabilities": inventory_prediction["classProbabilities"], "predictedClass": inventory_prediction["predictedClass"], "confidence": inventory_prediction["confidence"], "predictionConfidence": inventory_prediction["confidence"], "latencyMs": inventory_prediction["latencyMs"]})
        logger.debug("Inventario WebSocket payload: status=%s image=%s image_chars=%s slots=%s predicted=%s confidence=%s", inventory_payload.get("status"), bool(inventory_payload.get("inventoryImage")), len(inventory_payload.get("inventoryImage") or ""), len(inventory_payload.get("items", [])), inventory_payload.get("predictedClass"), inventory_payload.get("confidence"))
        await self.publish(session_id, "inventory.updated", inventory_payload, inventory["status"])
        # El modelo de fusiÃ³n activo fue entrenado con `audio` de espectrograma.
        # `audio_raw` es una modalidad distinta (waveform) y no puede ocupar ese
        # vector sin una fusiÃ³n reentrenada y validada. Se mantiene publicado como
        # seÃ±al independiente, pero no contamina la entrada de la fusiÃ³n activa.
        for modality in ("map", "sequence"):
            model_name = "frames" if modality == "sequence" else modality
            prediction = predictions[model_name]
            if prediction.get("status") != "ready":
                continue
            payload = {"winProbability": prediction["binary"]["winProbability"], "lossProbability": prediction["binary"]["lossProbability"], "classProbabilities": prediction["classProbabilities"], "confidence": prediction["confidence"], "latencyMs": prediction["latencyMs"], "modelVersion": prediction["modelVersion"]}
            if modality == "map":
                payload["image"] = await asyncio.to_thread(self._image_data_uri, crops["map"])
                await self.publish(session_id, "map.updated", payload, "ready")
            else:
                frame_images = await asyncio.gather(*(asyncio.to_thread(self._image_data_uri, value) for value in history[-6:]))
                payload["frames"] = [{"id": f"frame-{index}", "index": index, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "ready", "image": image} for index, image in enumerate(frame_images, start=1)]
                await self.publish(session_id, "frame_sequence.updated", payload, "ready")
        fusion = await asyncio.to_thread(self.inference.fuse, predictions)
        if fusion.get("status") == "ready":
            probabilities = fusion["classProbabilities"]
            risk_active = bool((smoothed_risk is not None and smoothed_risk >= 0.65) or safety.get("active"))
            await self.publish(session_id, "main_prediction.updated", {"predictedClass": frontend_class_from_name(str(fusion["predictedClass"])), "classProbabilities": probabilities, "classOrder": ["Eliminado", "Eliminacion", "Victoria"], "predictionSource": "multimodal_fusion", "fallback": False, "eliminatedProbability": probabilities["Eliminado"], "eliminationProbability": probabilities["Eliminacion"], "victoryProbability": probabilities["Victoria"], "confidence": fusion["confidence"], "latencyMs": 0, "modelVersion": fusion["modelVersion"], "participatingModalities": fusion["participatingModalities"], "missingModalities": fusion["missingModalities"], "riskProbability": smoothed_risk, "riskStatus": "high" if risk_active else "normal", "riskLabel": "Riesgo alto de ser eliminado" if risk_active else None, "riskMode": "shadow" if risk_shadow.get("status") == "ready" else "safety_only", "safetyRule": safety}, "ready")
            recommendations = evaluate_prediction(session_id, float(probabilities["Eliminado"]), list(fusion["missingModalities"]))
            for recommendation in recommendations:
                await self.publish(session_id, "recommendation.updated", recommendation, "ready")
