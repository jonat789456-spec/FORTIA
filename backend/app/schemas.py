from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ModuleStatus = Literal["idle", "waiting", "processing", "ready", "available", "stale", "low_confidence", "not_detected", "not_applicable", "unavailable", "error", "offline", "reconnecting"]
SessionStatus = Literal["idle", "waiting", "analyzing", "paused", "finished", "offline", "reconnecting"]
MainClass = Literal["eliminated", "elimination", "victory"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class EventMeta(ApiModel):
    contractVersion: str = "1.1"
    sessionId: str
    eventId: str = Field(default_factory=lambda: f"evt-{uuid4().hex}")
    predictionId: str = Field(default_factory=lambda: f"pred-{uuid4().hex}")
    timestamp: datetime = Field(default_factory=utc_now)
    source: str
    modality: str | None = None
    status: ModuleStatus = "waiting"
    modelVersion: str | None = None
    latencyMs: float | None = None


class SessionCreateResponse(ApiModel):
    sessionId: str
    status: SessionStatus


class SessionState(ApiModel):
    sessionId: str
    status: SessionStatus
    createdAt: datetime
    updatedAt: datetime
    participatingModalities: list[str] = Field(default_factory=list)
    lastError: str | None = None


class SystemStatus(ApiModel):
    status: Literal["ok", "degraded", "error"]
    service: str = "fortnite-ia-backend"
    version: str = "0.1.0"
    captureAvailable: bool = False
    gpuAvailable: bool = False
    loadedModels: list[str] = Field(default_factory=list)
    unavailableModels: list[str] = Field(default_factory=list)


class ModelStatus(ApiModel):
    name: str
    version: str | None = None
    status: str
    artifact: str | None = None


class WsEnvelope(ApiModel):
    type: str
    meta: EventMeta
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
