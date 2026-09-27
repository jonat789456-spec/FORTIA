from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings


class ModelRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.model_registry
        if not self.path.is_absolute():
            self.path = Path(__file__).resolve().parents[1] / self.path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"registryVersion": "1.0", "models": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def statuses(self) -> tuple[list[str], list[str]]:
        loaded: list[str] = []
        unavailable: list[str] = []
        for name, item in self.load().get("models", {}).items():
            artifact = Path(item.get("artifact", ""))
            if not artifact.is_absolute():
                artifact = Path(__file__).resolve().parents[1] / artifact
            if artifact.exists() and item.get("status") == "validated_on_validation":
                loaded.append(name)
            else:
                unavailable.append(name)
        return loaded, unavailable


registry = ModelRegistry()

