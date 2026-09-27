"""Mide latencia de los cargadores actuales sin evaluar el conjunto test."""

from __future__ import annotations

import json
import platform
import statistics
import time
from pathlib import Path

import numpy as np

from app.inference.service import InferenceService


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "backend" / "reports" / "performance" / "inference_benchmark.json"


def main() -> int:
    service = InferenceService()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {
        "testUsed": False,
        "inputData": "Vectores cero únicamente para medir tiempo; no se reportan predicciones.",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "models": {},
    }
    for modality, model in service.models.items():
        features = np.zeros((1, int(model.n_features_in_)), dtype=np.float32)
        for _ in range(3):
            service.predict(modality, features)
        latencies = []
        for _ in range(20):
            started = time.perf_counter()
            service.predict(modality, features)
            latencies.append((time.perf_counter() - started) * 1000)
        results["models"][modality] = {
            "samples": len(latencies),
            "meanMs": statistics.mean(latencies),
            "p95Ms": sorted(latencies)[int(len(latencies) * 0.95) - 1],
            "minMs": min(latencies),
            "maxMs": max(latencies),
            "modelVersion": service.versions.get(modality),
        }
    if service.fusion_model is not None:
        predictions = {modality: service.predict(modality, np.zeros((1, int(service.models[modality].n_features_in_)), dtype=np.float32)) for modality in ("frames", "health", "inventory", "map")}
        for _ in range(3):
            service.fuse(predictions)
        latencies = []
        for _ in range(20):
            started = time.perf_counter()
            service.fuse(predictions)
            latencies.append((time.perf_counter() - started) * 1000)
        results["models"]["fusion"] = {"samples": len(latencies), "meanMs": statistics.mean(latencies), "p95Ms": sorted(latencies)[int(len(latencies) * 0.95) - 1], "minMs": min(latencies), "maxMs": max(latencies), "modelVersion": service.versions.get("fusion")}
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
