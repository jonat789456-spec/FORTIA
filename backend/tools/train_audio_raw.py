"""Entrena el baseline de audio crudo usando solo train y validation.

La clase ``RawAudioClassifier`` calcula la representación en memoria a partir
de la onda. No lee ni modifica espectrogramas PNG y nunca usa ``test`` para
seleccionar el modelo.
"""
from __future__ import annotations

import json
import sys
import time
import wave
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, log_loss, precision_recall_fscore_support

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audio.model import RawAudioClassifier, RawAudioConfig


ROOT = Path(__file__).resolve().parents[2]
SEGMENTS = ROOT / "backend" / "data" / "manifests" / "audio_segments.csv"
ARTIFACT = ROOT / "backend" / "artifacts" / "audio_raw" / "audio_raw_logistic.joblib"
REPORT = ROOT / "backend" / "reports" / "audio_raw"


def read_wave(path: str, start: float, duration: float, config: RawAudioConfig) -> np.ndarray:
    with wave.open(path, "rb") as source:
        source.setpos(min(source.getnframes(), int(start * source.getframerate())))
        values = np.frombuffer(source.readframes(int(duration * source.getframerate())), dtype="<i2").astype(np.float32) / 32768.0
    target = int(config.sample_rate * config.window_sec)
    if values.size < target:
        values = np.pad(values, (0, target - values.size))
    return values[:target]


def metrics(model: RawAudioClassifier, x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    probabilities = model.predict_proba(x)
    predicted = model.classes_[probabilities.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(y, predicted, labels=[0, 1, 2], zero_division=0)
    return {"samples": int(len(y)), "accuracy": float(accuracy_score(y, predicted)), "balanced_accuracy": float(balanced_accuracy_score(y, predicted)), "f1_macro": float(f1_score(y, predicted, average="macro", zero_division=0)), "f1_weighted": float(f1_score(y, predicted, average="weighted", zero_division=0)), "log_loss": float(log_loss(y, probabilities, labels=[0, 1, 2])), "precision": dict(zip(["Eliminado", "Eliminacion", "Victoria"], [float(value) for value in precision])), "recall": dict(zip(["Eliminado", "Eliminacion", "Victoria"], [float(value) for value in recall])), "f1": dict(zip(["Eliminado", "Eliminacion", "Victoria"], [float(value) for value in f1])), "support": dict(zip(["Eliminado", "Eliminacion", "Victoria"], [int(value) for value in support]))}


def main() -> int:
    started = time.perf_counter()
    frame = pd.read_csv(SEGMENTS, encoding="utf-8-sig")
    frame = frame[(frame.status == "valid") & frame.audio_path.notna()]
    if ARTIFACT.exists():
        saved = joblib.load(ARTIFACT)
        metrics_saved = saved.get("validation_metrics", {})
        payload = {"artifact": str(ARTIFACT.relative_to(ROOT / "backend")), "model": "RawAudioClassifier(LogisticRegression)", "train_segments": int((frame.split == "train").sum()), "validation_segments": int((frame.split == "validation").sum()), "test_segments": int((frame.split == "test").sum()), "validation": metrics_saved, "elapsed_sec": 0.0, "test_used_for_selection": False}
        REPORT.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value))
        (REPORT / "raw_model_metrics.json").write_text(serialized, encoding="utf-8")
        (REPORT / "RAW_MODEL_REPORT.md").write_text("# Modelo de audio crudo\n\n" + serialized, encoding="utf-8")
        print(serialized)
        return 0
    config = RawAudioConfig()
    arrays, labels, splits = [], [], []
    for row in frame.itertuples():
        arrays.append(read_wave(row.audio_path, float(row.start_sec), config.window_sec, config))
        labels.append(int(row.label)); splits.append(row.split)
    x = np.stack(arrays).astype(np.float32)
    y = np.asarray(labels, dtype=np.int64)
    split_values = np.asarray(splits)
    train = split_values == "train"
    validation = split_values == "validation"
    model = RawAudioClassifier(LogisticRegression(max_iter=500, class_weight="balanced", random_state=42), config)
    model.fit(x[train], y[train])
    validation_metrics = metrics(model, x[validation], y[validation])
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True); REPORT.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "model_type": "raw_waveform_internal_logmel_logistic", "version": "audio-raw-0.1.0", "sample_rate": config.sample_rate, "window_sec": config.window_sec, "classes": [0, 1, 2], "selection_split": "validation", "test_used_for_selection": False, "validation_metrics": validation_metrics}, ARTIFACT)
    payload = {"artifact": str(ARTIFACT.relative_to(ROOT / "backend")), "model": "RawAudioClassifier(LogisticRegression)", "train_segments": int(train.sum()), "validation_segments": int(validation.sum()), "test_segments": int((split_values == "test").sum()), "validation": validation_metrics, "elapsed_sec": round(time.perf_counter() - started, 3), "test_used_for_selection": False}
    (REPORT / "raw_model_metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORT / "RAW_MODEL_REPORT.md").write_text("# Modelo de audio crudo\n\n" + json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
