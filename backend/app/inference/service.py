from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..model_registry import ModelRegistry
from ..prediction_adapter import three_class_to_frontend


CLASS_NAMES = {0: "Eliminado", 1: "Eliminacion", 2: "Victoria"}


class InferenceService:
    """Carga los artefactos una vez y ejecuta inferencia sin tocar el dataset."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.models: dict[str, Any] = {}
        self.fusion_model: Any | None = None
        self.fusion_metadata: dict[str, Any] = {}
        self.versions: dict[str, str] = {}
        self.load_errors: dict[str, str] = {}
        self._load_once()

    def _load_once(self) -> None:
        for name, item in self.registry.load().get("models", {}).items():
            artifact = Path(item.get("artifact", ""))
            if not artifact.is_absolute():
                artifact = Path(__file__).resolve().parents[2] / artifact
            if name == "fusion" or artifact.suffix != ".joblib":
                if name == "fusion" and artifact.suffix == ".joblib":
                    try:
                        payload = joblib.load(artifact)
                        self.fusion_model = payload["model"]
                        self.fusion_metadata = payload
                        self.versions["fusion"] = str(item.get("version", payload.get("version", "unknown")))
                    except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
                        self.load_errors["fusion"] = str(exc)
                continue
            try:
                self.models[name] = joblib.load(artifact)["model"]
                self.versions[name] = str(item.get("version", "unknown"))
            except (FileNotFoundError, OSError, KeyError, ValueError) as exc:
                self.load_errors[name] = str(exc)

    def status(self) -> dict[str, Any]:
        return {"loaded": sorted(self.models), "errors": self.load_errors.copy(), "loadCount": 1}

    def predict(self, modality: str, features: np.ndarray) -> dict[str, Any]:
        model = self.models.get(modality)
        if model is None:
            return {"status": "unavailable", "modality": modality, "reason": self.load_errors.get(modality, "Modelo no cargado")}
        started = time.perf_counter()
        array = np.asarray(features, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        expected = getattr(model, "n_features_in_", None)
        if expected is not None and array.shape[1] != expected:
            return {"status": "error", "modality": modality, "reason": f"Forma inválida: recibida {array.shape[1]}, esperada {expected}"}
        probabilities = model.predict_proba(array)[0]
        by_class = {CLASS_NAMES[int(label)]: float(value) for label, value in zip(model.classes_, probabilities)}
        normalized = {name: by_class.get(name, 0.0) for name in CLASS_NAMES.values()}
        return {
            "status": "ready",
            "modality": modality,
            "classProbabilities": normalized,
            "predictedClass": CLASS_NAMES[int(model.classes_[int(np.argmax(probabilities))])],
            "confidence": float(np.max(probabilities)),
            "binary": three_class_to_frontend(normalized),
            "latencyMs": (time.perf_counter() - started) * 1000,
            "modelVersion": self.versions.get(modality),
        }

    def fuse(self, predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        ready = {name: value for name, value in predictions.items() if value.get("status") == "ready"}
        if "frames" not in ready:
            return {"status": "unavailable", "reason": "La secuencia de seis frames es obligatoria para la fusión", "participatingModalities": sorted(ready), "missingModalities": ["frames"]}
        if self.fusion_model is not None:
            feature_names = self.fusion_metadata.get("feature_names", [])
            vector: list[float] = []
            for modality in ("frames", "health", "inventory", "map", "audio"):
                item = ready.get(modality)
                vector.extend([float(item["classProbabilities"].get(name, 0.0)) for name in CLASS_NAMES.values()] if item else [0.0, 0.0, 0.0])
            vector.extend([1.0 if modality in ready else 0.0 for modality in ("frames", "health", "inventory", "map", "audio")])
            if len(vector) == len(feature_names):
                probabilities = self.fusion_model.predict_proba(np.asarray(vector, dtype=np.float32).reshape(1, -1))[0]
            else:
                return {"status": "error", "reason": "El orden de características de la fusión no coincide con el registro", "participatingModalities": sorted(ready), "missingModalities": sorted(set(self.models) - set(ready))}
        else:
            matrix = np.asarray([[item["classProbabilities"][name] for name in CLASS_NAMES.values()] for item in ready.values()], dtype=np.float32)
            probabilities = matrix.mean(axis=0)
        probabilities = probabilities / probabilities.sum()
        names = list(CLASS_NAMES.values())
        index = int(np.argmax(probabilities))
        return {
            "status": "ready",
            "classProbabilities": dict(zip(names, probabilities.astype(float))),
            "predictedClass": names[index],
            "confidence": float(probabilities[index]),
            "participatingModalities": sorted(ready),
            "missingModalities": sorted(set(self.models) - set(ready)),
            "binary": three_class_to_frontend(dict(zip(names, probabilities.astype(float)))),
            "modelVersion": self.versions.get("fusion", "fusion-baseline-0.1.0"),
        }
