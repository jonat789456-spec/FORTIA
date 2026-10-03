from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Any


class FailureRecorder:
    """Persistencia opt-in, acotada y deduplicada de casos difíciles.

    El recorder está desactivado por defecto. Solo almacena un caso cuando el
    resultado real es conocido o cuando se llama explícitamente a
    ``record_case``; no convierte una predicción en etiqueta.
    """

    def __init__(self, root: Path, enabled: bool = False, max_cases: int = 500) -> None:
        self.root = root
        self.enabled = enabled
        self.max_cases = max_cases
        self.cases_path = root / "cases.jsonl"
        self.frames_root = root / "frames"
        self._lock = Lock()
        self._recent: deque[str] = deque(maxlen=max_cases)
        if enabled:
            root.mkdir(parents=True, exist_ok=True)
            self._load_recent()

    def _load_recent(self) -> None:
        if not self.cases_path.exists():
            return
        lines = self.cases_path.read_text(encoding="utf-8").splitlines()[-self.max_cases :]
        for line in lines:
            try:
                self._recent.append(str(json.loads(line)["dedupeKey"]))
            except (ValueError, KeyError, TypeError):
                continue

    @staticmethod
    def _key(case: dict[str, Any]) -> str:
        source = "|".join(str(case.get(key, "")) for key in ("sessionId", "result", "timestamp", "eventType"))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]

    def record_case(self, case: dict[str, Any], frames: list[bytes] | None = None) -> bool:
        if not self.enabled:
            return False
        payload = dict(case)
        payload.setdefault("recordedAt", time.time())
        payload["dedupeKey"] = self._key(payload)
        with self._lock:
            if payload["dedupeKey"] in self._recent:
                return False
            if frames:
                frame_dir = self.frames_root / payload["dedupeKey"]
                frame_dir.mkdir(parents=True, exist_ok=True)
                references = []
                for index, frame in enumerate(frames[-6:], start=1):
                    path = frame_dir / f"frame_{index:02d}.jpg"
                    path.write_bytes(frame)
                    references.append(str(path.relative_to(self.root)))
                payload["previousFrames"] = references
            with self.cases_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._recent.append(payload["dedupeKey"])
            self._trim()
            return True

    def _trim(self) -> None:
        if not self.cases_path.exists():
            return
        lines = self.cases_path.read_text(encoding="utf-8").splitlines()
        if len(lines) > self.max_cases:
            self.cases_path.write_text("\n".join(lines[-self.max_cases :]) + "\n", encoding="utf-8")
