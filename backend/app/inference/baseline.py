from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np


class BaselinePredictor:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        payload: dict[str, Any] = joblib.load(artifact)
        self.model = payload["model"]
        self.modality = payload["modality"]
        self.classes = payload.get("classes", [0, 1, 2])

    def predict(self, features: np.ndarray) -> dict[str, Any]:
        probabilities = self.model.predict_proba(features)[0]
        aligned = {str(label): 0.0 for label in self.classes}
        for label, value in zip(self.model.classes_, probabilities):
            aligned[str(int(label))] = float(value)
        predicted = max(aligned, key=aligned.get)
        return {"modality": self.modality, "classCode": int(predicted), "probabilities": aligned, "status": "ready"}

