from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .capture.windows import capture_capability
from .config import settings
from .model_registry import registry
from .runtime.events import EventHub
from .runtime.pipeline import RuntimePipeline
from .schemas import ModelStatus, SessionCreateResponse, SessionState, SystemStatus
from .sessions import sessions


app = FastAPI(title="Fortnite IA Backend", version="0.1.0")
allowed_frontend_origins = list(dict.fromkeys([
    settings.frontend_origin,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
event_hub = EventHub()
runtime_pipeline = RuntimePipeline(event_hub.publish)


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
    return SystemStatus(status="ok" if loaded and capture_available else "degraded", captureAvailable=capture_available, gpuAvailable=gpu_available(), loadedModels=loaded, unavailableModels=unavailable)


@app.get("/api/v1/models", response_model=list[ModelStatus])
def model_status() -> list[ModelStatus]:
    payload = registry.load().get("models", {})
    loaded, _ = registry.statuses()
    return [ModelStatus(name=name, version=item.get("version"), status="ready" if name in loaded else "unavailable", artifact=item.get("artifact")) for name, item in payload.items()]


@app.get("/api/v1/config")
def backend_config() -> dict[str, object]:
    return {"captureFps": settings.capture_fps, "streamFps": settings.stream_fps, "inferenceIntervalSec": settings.inference_interval_sec, "captureMode": settings.capture_mode, "captureWindowTitle": settings.capture_window_title, "captureProcessName": settings.capture_process_name or None, "contractVersion": "1.1"}


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
    except WebSocketDisconnect:
        await event_hub.remove(session_id, websocket)
