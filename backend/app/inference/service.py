from __future__ import annotations

import time
import hashlib
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..model_registry import ModelRegistry
from ..prediction_adapter import three_class_to_frontend
from ..class_mapping import CLASS_NAMES, align_probabilities, class_name_from_code
from .risk import safety_signal


class InferenceService:
    """Carga los artefactos una vez y ejecuta inferencia sin tocar el dataset."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.models: dict[str, Any] = {}
        self.fusion_model: Any | None = None
        self.fusion_metadata: dict[str, Any] = {}
        self.versions: dict[str, str] = {}
        self.load_errors: dict[str, str] = {}
        self.raw_audio_model: Any | None = None
        self.risk_model: Any | None = None
        self.risk_metadata: dict[str, Any] = {}
        self._load_risk_experiment()
        self._load_once()

    def diagnostics(self) -> dict[str, Any]:
        result: dict[str, Any] = {"models": {}, "fusion": self.fusion_metadata.get("version"), "mode": "real"}
        for name, item in self.registry.load().get("models", {}).items():
            artifact = Path(item.get("artifact", ""))
            if not artifact.is_absolute():
                artifact = Path(__file__).resolve().parents[2] / artifact
            entry: dict[str, Any] = {"path": str(artifact.resolve()), "version": self.versions.get(name, item.get("version")), "exists": artifact.exists()}
            if artifact.exists():
                entry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
                entry["modified"] = artifact.stat().st_mtime
            model = self.models.get(name)
            if model is not None:
                entry["inputFeatures"] = getattr(model, "n_features_in_", None)
                entry["outputClasses"] = [int(value) for value in getattr(model, "classes_", [])]
            result["models"][name] = entry
        result["classOrder"] = {str(index): name for index, name in enumerate(CLASS_NAMES)}
        result["fusionFeatures"] = self.fusion_metadata.get("feature_names", [])
        result["calibrator"] = self.fusion_metadata.get("calibrator")
        return result

    def _load_risk_experiment(self) -> None:
        from ..config import settings
        if not settings.risk_shadow_enabled:
            return
        artifact = settings.risk_experiment_artifact
        if not artifact.is_absolute():
            artifact = Path(__file__).resolve().parents[2] / artifact
        try:
            payload = joblib.load(artifact)
            self.risk_model = payload["model"]
            self.risk_metadata = payload
            self.versions["risk_shadow"] = str(payload.get("version", "unknown"))
        except (FileNotFoundError, OSError, KeyError, ValueError, ModuleNotFoundError) as exc:
            self.load_errors["risk_shadow"] = str(exc)

    def _load_once(self) -> None:
        for name, item in self.registry.load().get("models", {}).items():
            artifact = Path(item.get("artifact", ""))
            if not artifact.is_absolute():
                artifact = Path(__file__).resolve().parents[2] / artifact
            if name == "audio_raw":
                try:
                    self.raw_audio_model = joblib.load(artifact)["model"]
                    self.versions[name] = str(item.get("version", "unknown"))
                except (FileNotFoundError, OSError, KeyError, ValueError, ModuleNotFoundError) as exc:
                    self.load_errors[name] = str(exc)
                continue
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
        loaded = set(self.models)
        if self.raw_audio_model is not None:
            loaded.add("audio_raw")
        return {"loaded": sorted(loaded), "errors": self.load_errors.copy(), "loadCount": 1}

    def predict_risk_shadow(self, features: dict[str, float | None]) -> dict[str, Any]:
        if self.risk_model is None:
            return {"status": "disabled", "mode": "shadow", "reason": "Experimento de riesgo no habilitado"}
        names = self.risk_metadata.get("feature_names", [])
        vector = np.asarray([[float(features.get(name)) if features.get(name) is not None else 0.0 for name in names]], dtype=np.float32)
        started = time.perf_counter()
        probabilities = self.risk_model.predict_proba(vector)[0]
        index = list(self.risk_model.classes_).index(1) if 1 in self.risk_model.classes_ else int(np.argmax(probabilities))
        return {"status": "ready", "mode": "shadow", "riskProbability": float(probabilities[index]), "modelVersion": self.versions.get("risk_shadow"), "latencyMs": (time.perf_counter() - started) * 1000, "featuresUsed": names}

    @staticmethod
    def safety_signal(features: dict[str, float | None]) -> dict[str, Any]:
        return safety_signal(features)

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
        normalized = align_probabilities([int(label) for label in model.classes_], [float(value) for value in probabilities])
        return {
            "status": "ready",
            "modality": modality,
            "classProbabilities": normalized,
            "predictedClass": class_name_from_code(int(model.classes_[int(np.argmax(probabilities))])),
            "confidence": float(np.max(probabilities)),
            "binary": three_class_to_frontend(normalized),
            "latencyMs": (time.perf_counter() - started) * 1000,
            "modelVersion": self.versions.get(modality),
        }

    def predict_audio_waveform(self, waveform: np.ndarray, quality: dict[str, object] | None = None) -> dict[str, Any]:
        """Predice desde waveform; no acepta una imagen ni un vector PNG."""
        if self.raw_audio_model is None:
            return {"status": "model_missing", "modality": "audio", "source": "wasapi_loopback", "reason": self.load_errors.get("audio_raw", "Modelo de audio no encontrado"), "quality": quality or {}}
        quality = quality or {}
        if bool(quality.get("silence")):
            return {"status": "silence", "modality": "audio", "source": "wasapi_loopback", "reason": "Ventana silenciosa; no se inventa una predicción", "quality": quality, "modelVersion": self.versions.get("audio_raw")}
        started = time.perf_counter()
        try:
            probabilities = self.raw_audio_model.predict_proba(np.asarray(waveform, dtype=np.float32).reshape(1, -1))[0]
        except (ValueError, RuntimeError, OSError) as exc:
            return {"status": "error", "modality": "audio", "source": "wasapi_loopback", "reason": str(exc), "quality": quality}
        normalized = align_probabilities([int(label) for label in self.raw_audio_model.classes_], [float(value) for value in probabilities])
        predicted = max(normalized, key=normalized.get)
        confidence = normalized[predicted]
        return {"status": "ready" if confidence >= 0.55 else "low_confidence", "modality": "audio", "source": "wasapi_loopback", "classProbabilities": normalized, "predictedClass": predicted, "confidence": confidence, "binary": three_class_to_frontend(normalized), "quality": quality, "silence": False, "latencyMs": (time.perf_counter() - started) * 1000, "modelVersion": self.versions.get("audio_raw")}

    def fuse(self, predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        ready = {name: value for name, value in predictions.items() if value.get("status") == "ready"}
        if "frames" not in ready:
            return {"status": "unavailable", "reason": "La secuencia de seis frames es obligatoria para la fusión", "participatingModalities": sorted(ready), "missingModalities": ["frames"]}
        if self.fusion_model is not None:
            feature_names = self.fusion_metadata.get("feature_names", [])
            vector: list[float] = []
            for modality in ("frames", "health", "inventory", "map", "audio"):
                item = ready.get(modality)
                vector.extend([float(item["classProbabilities"].get(name, 0.0)) for name in CLASS_NAMES] if item else [0.0, 0.0, 0.0])
            vector.extend([1.0 if modality in ready else 0.0 for modality in ("frames", "health", "inventory", "map", "audio")])
            if len(vector) == len(feature_names):
                probabilities = self.fusion_model.predict_proba(np.asarray(vector, dtype=np.float32).reshape(1, -1))[0]
            else:
                return {"status": "error", "reason": "El orden de características de la fusión no coincide con el registro", "participatingModalities": sorted(ready), "missingModalities": sorted(set(self.models) - set(ready))}
        else:
            return {"status": "unavailable", "reason": "El artefacto de fusiÃ³n no estÃ¡ disponible; no se usa promedio heurÃ­stico", "participatingModalities": sorted(ready), "missingModalities": ["fusion"]}
        probabilities = probabilities / probabilities.sum()
        names = list(CLASS_NAMES)
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
