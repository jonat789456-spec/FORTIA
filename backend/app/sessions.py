from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from .schemas import SessionState, SessionStatus


def now() -> datetime:
    return datetime.now(timezone.utc)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()

    def create(self) -> SessionState:
        timestamp = now()
        session = SessionState(sessionId=f"session-{uuid4().hex}", status="idle", createdAt=timestamp, updatedAt=timestamp)
        with self._lock:
            self._sessions[session.sessionId] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def transition(self, session_id: str, status: SessionStatus) -> SessionState | None:
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                return None
            updated = current.model_copy(update={"status": status, "updatedAt": now()})
            self._sessions[session_id] = updated
            return updated


sessions = SessionManager()

