from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import logging

from .capture.windows import capture_capability
from .audio.capture import loopback_capability
from .config import settings
from .model_registry import registry
from .runtime.events import EventHub
from .runtime.pipeline import RuntimePipeline
from .schemas import ModelStatus, SessionCreateResponse, SessionState, SystemStatus
from .sessions import sessions


app = FastAPI(title="Fortnite IA Backend", version="0.1.0")
allowed_frontend_origins = list(dict.fromkeys([
    settings.frontend_origin,
    *[origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()],
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
event_hub = EventHub()
runtime_pipeline = RuntimePipeline(event_hub.publish, publish_binary=event_hub.publish_binary)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_diagnostics() -> None:
    audio = loopback_capability()
    logger.info("Modelos cargados al iniciar: %s", registry.statuses())
    logger.info("Diagnóstico reproducible de artefactos: %s", runtime_pipeline.inference.diagnostics())
    logger.info("Dispositivos WASAPI Loopback al iniciar: %s", audio)


def gpu_available() -> bool:
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except (ImportError, OSError, RuntimeError):
        return False


@app.get("/api/v1/system/status", response_model=SystemStatus)
def system_status() -> SystemStatus:
    loaded, unavailable = registry.statuses()
    capture_available = bool(capture_capability()["available"])
    audio = loopback_capability()
    return SystemStatus(status="ok" if loaded and capture_available else "degraded", captureAvailable=capture_available, gpuAvailable=gpu_available(), loadedModels=loaded, unavailableModels=unavailable, audioCapture=audio)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/models", response_model=list[ModelStatus])
def model_status() -> list[ModelStatus]:
    payload = registry.load().get("models", {})
    loaded, _ = registry.statuses()
    return [ModelStatus(name=name, version=item.get("version"), status="ready" if name in loaded else "unavailable", artifact=item.get("artifact")) for name, item in payload.items()]


@app.get("/api/v1/config")
def backend_config() -> dict[str, object]:
    return {"captureFps": settings.capture_fps, "streamFps": settings.stream_fps, "healthFastFps": settings.health_fast_fps, "healthVisibleFps": settings.health_visible_fps, "healthCurrentMaxAgeSec": settings.health_current_max_age_sec, "streamAdaptive": settings.stream_adaptive, "streamMinFps": settings.stream_min_fps, "streamMaxWidth": settings.stream_max_width, "streamFallbackWidth": settings.stream_fallback_width, "streamJpegQuality": settings.stream_jpeg_quality, "inferenceIntervalSec": settings.inference_interval_sec, "captureMode": settings.capture_mode, "captureWindowTitle": settings.capture_window_title, "captureProcessName": settings.capture_process_name or None, "audioOutputDevice": settings.audio_output_device or None, "contractVersion": "1.1"}


@app.get("/api/v1/audio/devices")
def audio_devices() -> dict[str, object]:
    return loopback_capability()


@app.post("/api/v1/sessions", response_model=SessionCreateResponse)
def create_session() -> SessionCreateResponse:
    session = sessions.create()
    return SessionCreateResponse(sessionId=session.sessionId, status=session.status)


def transition(session_id: str, status: str) -> SessionState:
    result = sessions.transition(session_id, status)  # type: ignore[arg-type]
    if result is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return result


@app.post("/api/v1/sessions/{session_id}/start", response_model=SessionState)
async def start_session(session_id: str) -> SessionState:
    result = transition(session_id, "analyzing")
    await runtime_pipeline.start(session_id)
    await event_hub.publish(session_id, "session.status", {"sessionStatus": result.status}, "ready")
    return result


@app.post("/api/v1/sessions/{session_id}/frames")
async def ingest_web_frame(session_id: str, request: Request) -> dict[str, object]:
    """Recibe un JPEG reducido desde ``getDisplayMedia`` del navegador."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].casefold()
    if content_type not in {"image/jpeg", "image/webp", "image/png"}:
        raise HTTPException(status_code=415, detail="Solo se aceptan frames de imagen comprimidos")
    declared_length = request.headers.get("content-length")
    try:
        if declared_length and int(declared_length) > settings.web_frame_max_bytes:
            raise HTTPException(status_code=413, detail="El frame supera el tamaño permitido")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Content-Length inválido") from exc
    body = await request.body()
    if not body or len(body) > settings.web_frame_max_bytes:
        raise HTTPException(status_code=413, detail="El frame supera el tamaño permitido")
    try:
        from io import BytesIO
        import numpy as np
        from PIL import Image

        image = Image.open(BytesIO(body)).convert("RGB")
        if max(image.size) > settings.web_frame_max_width:
            ratio = settings.web_frame_max_width / max(image.size)
            image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.BILINEAR)
        frame = np.asarray(image, dtype=np.uint8).copy()
        return await runtime_pipeline.ingest_web_frame(session_id, frame)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Frame inválido") from exc


@app.post("/api/v1/sessions/{session_id}/pause", response_model=SessionState)
async def pause_session(session_id: str) -> SessionState:
    await runtime_pipeline.stop(session_id)
    result = transition(session_id, "paused")
    await event_hub.publish(session_id, "session.status", {"sessionStatus": result.status}, "ready")
    return result


@app.post("/api/v1/sessions/{session_id}/resume", response_model=SessionState)
async def resume_session(session_id: str) -> SessionState:
    result = transition(session_id, "analyzing")
    await runtime_pipeline.start(session_id)
    await event_hub.publish(session_id, "session.status", {"sessionStatus": result.status}, "ready")
    return result


@app.post("/api/v1/sessions/{session_id}/finish", response_model=SessionState)
async def finish_session(session_id: str) -> SessionState:
    await runtime_pipeline.stop(session_id)
    result = transition(session_id, "finished")
    await event_hub.publish(session_id, "session.status", {"sessionStatus": result.status}, "ready")
    return result


@app.post("/api/v1/sessions/{session_id}/reset", response_model=SessionState)
async def reset_session(session_id: str) -> SessionState:
    await runtime_pipeline.stop(session_id)
    result = transition(session_id, "idle")
    await event_hub.publish(session_id, "session.status", {"sessionStatus": result.status}, "ready")
    return result


@app.get("/api/v1/sessions/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return session


@app.get("/api/v1/sessions/{session_id}/summary")
def session_summary(session_id: str) -> dict[str, object]:
    session = get_session(session_id)
    events = event_hub.history(session_id)
    recommendations = [event["data"] for event in events if event.get("type") == "recommendation.updated"]
    return {"session": session.model_dump(mode="json"), "events": events, "recommendations": recommendations}


@app.post("/api/v1/sessions/{session_id}/outcome")
async def record_real_outcome(session_id: str, outcome: dict[str, object]) -> dict[str, object]:
    """Punto de recolección opt-in; no etiqueta automáticamente predicciones."""
    get_session(session_id)
    return await runtime_pipeline.record_outcome(session_id, outcome)


@app.websocket("/api/v1/ws/sessions/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str) -> None:
    session = sessions.get(session_id)
    if session is None:
        await websocket.close(code=4404, reason="Sesión no encontrada")
        return
    await websocket.accept()
    await event_hub.add(session_id, websocket)
    await event_hub.publish(session_id, "session.status", {"sessionStatus": session.status}, "ready")
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await event_hub.publish(session_id, "system.pong", {"received": True}, "ready")
            elif message.get("type") == "audio.tts":
                runtime_pipeline.set_audio_suppressed(session_id, bool(message.get("active", False)))
    except (WebSocketDisconnect, RuntimeError):
        await event_hub.remove(session_id, websocket)


@app.websocket("/api/v1/ws/sessions/{session_id}/visual")
async def visual_websocket(websocket: WebSocket, session_id: str) -> None:
    """Canal exclusivo para frames binarios; no comparte la cola de predicciones."""
    session = sessions.get(session_id)
    if session is None:
        await websocket.close(code=4404, reason="SesiÃ³n no encontrada")
        return
    await websocket.accept()
    await event_hub.add(session_id, websocket, role="visual")
    try:
        while True:
            await websocket.receive()
    except (WebSocketDisconnect, RuntimeError):
        await event_hub.remove(session_id, websocket)
