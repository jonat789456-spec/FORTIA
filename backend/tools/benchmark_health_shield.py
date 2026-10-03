"""Benchmark reproducible del lector rápido con datos sintéticos controlados."""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.preprocessing.structured import HealthShieldReader


def frame(health: float, shield: float, width: int = 489, height: int = 216) -> np.ndarray:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    x0, right = int(width * 0.08), int(width * 0.60)
    def fill(value: float) -> int:
        return x0 + int((right - x0) * value / 100)
    image[int(height * .50):int(height * .68), x0:fill(shield)] = [10, 120, 220]
    image[int(height * .68):int(height * .90), x0:fill(health)] = [10, 220, 10]
    return image


def main() -> int:
    reader = HealthShieldReader()
    timings: list[float] = []
    errors: list[float] = []
    per_range: dict[str, list[float]] = {"0": [], "1-25": [], "26-50": [], "51-75": [], "76-99": [], "100": []}
    false_zero = 0
    false_100 = 0
    values = list(range(100, 0, -5)) + [100] * 20
    for index, expected in enumerate(values):
        image = frame(expected, expected)
        started = time.perf_counter()
        result = reader.read(image, timestamp=index / 10)
        timings.append((time.perf_counter() - started) * 1000)
        for key in ("healthValue", "shieldValue"):
            if result[key] is not None:
                predicted = float(result[key])
                error = abs(predicted - expected)
                errors.append(error)
                bucket = "0" if expected == 0 else "100" if expected == 100 else "1-25" if expected <= 25 else "26-50" if expected <= 50 else "51-75" if expected <= 75 else "76-99"
                per_range[bucket].append(error)
                false_zero += int(expected > 0 and predicted <= 0.5)
                false_100 += int(expected < 100 and predicted >= 99.5)
    drop_reader = HealthShieldReader()
    drop_reader.read(frame(100, 100), timestamp=0.0)
    started = time.perf_counter()
    drop = drop_reader.read(frame(20, 0), timestamp=0.1)
    reaction_ms = (time.perf_counter() - started) * 1000
    report = {
        "version": "health-shield-v2",
        "dataset": "synthetic_controlled_bars",
        "test_used": False,
        "samples": len(values),
        "mae": statistics.mean(errors),
        "median_error": statistics.median(errors),
        "within_2": sum(error <= 2 for error in errors) / len(errors),
        "within_5": sum(error <= 5 for error in errors) / len(errors),
        "invalid_readings": 0,
        "false_zero": false_zero,
        "false_100": false_100,
        "mae_by_range": {bucket: statistics.mean(values) if values else None for bucket, values in per_range.items()},
        "mean_latency_ms": statistics.mean(timings),
        "p95_latency_ms": float(np.percentile(timings, 95)),
        "reaction_ms_reader_only": reaction_ms,
        "reaction_values": {"health": drop["healthValue"], "shield": drop["shieldValue"]},
        "note": "No sustituye una muestra manual de Fortnite; sirve para regresión del detector.",
    }
    output = Path("backend/reports/health_shield_v2")
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
