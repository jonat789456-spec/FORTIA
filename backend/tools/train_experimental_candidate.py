"""Entrenamiento experimental aislado: solo train/validation, nunca test."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, f1_score,
                             log_loss, precision_recall_fscore_support)

from app.class_mapping import CLASS_NAMES
from tools.train_multimodal import build_features

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = BACKEND / "data" / "splits" / "video_split.csv"
MODALITIES = ("frames", "health", "inventory", "map", "audio")
LABELS = {"Eliminado": 0, "Eliminacion": 1, "Victoria": 2}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def weights(counts: dict[str, int], mode: str) -> dict[int, float] | None:
    if mode == "none":
        return None
    if mode == "sqrt_inverse":
        raw = {name: 1.0 / np.sqrt(count) for name, count in counts.items()}
    elif mode == "capped_balanced":
        raw = {name: min(496.0 / (3.0 * count), 3.0) for name, count in counts.items()}
    elif mode == "balanced_reference":
        raw = {name: 496.0 / (3.0 * count) for name, count in counts.items()}
    else:
        raise ValueError(mode)
    mean = sum(raw.values()) / len(raw)
    # Normalize and explicitly prevent an extreme Victoria weight.
    normalized = {index: value / mean for index, (name, value) in enumerate(raw.items())}
    if normalized[2] > 3.0:
        raise ValueError("peso extremo para Victoria rechazado")
    return normalized


def evaluate(model: LogisticRegression, x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    timings = []
    probabilities = model.predict_proba(x)
    for _ in range(100):
        start = time.perf_counter()
        model.predict_proba(x)
        timings.append((time.perf_counter() - start) * 1000.0 / max(1, len(y)))
    predicted = model.classes_[probabilities.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(
        y, predicted, labels=[0, 1, 2], zero_division=0
    )
    one_hot = np.eye(3, dtype=float)[y]
    brier = float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))
    return {
        "samples": int(len(y)),
        "precision": dict(zip(CLASS_NAMES, precision.astype(float))),
        "recall": dict(zip(CLASS_NAMES, recall.astype(float))),
        "f1": dict(zip(CLASS_NAMES, f1.astype(float))),
        "support": dict(zip(CLASS_NAMES, support.astype(int))),
        "macro_f1": float(f1_score(y, predicted, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1, 2]).tolist(),
        "prediction_distribution": {CLASS_NAMES[i]: int((predicted == i).sum()) for i in range(3)},
        "mean_probability": dict(zip(CLASS_NAMES, probabilities.mean(axis=0).astype(float))),
        "brier_score": brier,
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1, 2])),
        "latency_ms_mean": float(np.mean(timings)),
        "latency_ms_p95": float(np.percentile(timings, 95)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    artifact_dir = out / "models"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    if set(split["split"].astype(str)) - {"train", "validation", "test", "excluded_ambiguous"}:
        raise RuntimeError("split desconocido")
    train = split[split["split"] == "train"].copy()
    validation = split[split["split"] == "validation"].copy()
    if train.empty or validation.empty:
        raise RuntimeError("faltan train o validation")
    labels = {int(row.id_video): LABELS[str(row.clase)] for row in pd.concat([train, validation]).itertuples()}
    if set(labels.values()) != {0, 1, 2}:
        raise RuntimeError("mapeo de clases incompleto")
    print(f"CANDIDATO EXPERIMENTAL NO PROMOVIBLE")
    print(f"Dataset: split histórico {SPLIT}")
    print(f"Train: {len(train)} videos; validation: {len(validation)} videos; test leído: NO")
    print(f"Clases: {LABELS}")

    datasets = {
        "frames": (pd.read_csv(DF_ROOT / "df_frames.csv", encoding="utf-8-sig"), "ruta_imagen", True),
        "health": (pd.read_csv(DF_ROOT / "df_recortes_vida.csv", encoding="utf-8-sig"), "ruta_vida", False),
        "inventory": (pd.read_csv(DF_ROOT / "df_recortes_inventario.csv", encoding="utf-8-sig"), "ruta_inventario", False),
        "map": (pd.read_csv(DF_ROOT / "df_recortes_mapa.csv", encoding="utf-8-sig"), "ruta_mapa", False),
        "audio": (pd.read_csv(DF_ROOT / "df_audio.csv", encoding="utf-8-sig"), "ruta_espectrograma", False),
    }
    baseline_dir = BACKEND / "artifacts" / "baselines"
    models = {m: joblib.load(baseline_dir / f"{m}_logistic.joblib")["model"] for m in MODALITIES}
    train_ids = train["id_video"].astype(int).tolist()
    validation_ids = validation["id_video"].astype(int).tolist()
    train_x, train_y, feature_names = build_features(train_ids, labels, models, datasets)
    validation_x, validation_y, _ = build_features(validation_ids, labels, models, datasets)
    counts = {name: int((train_y == index).sum()) for index, name in enumerate(CLASS_NAMES)}
    print(f"Distribución train: {counts}")
    candidates = {name: weights(counts, name) for name in ("none", "sqrt_inverse", "capped_balanced", "balanced_reference")}
    report = {
        "status": "CANDIDATO EXPERIMENTAL NO PROMOVIBLE",
        "test_used": False,
        "dataset_limitations": ["etiquetas históricas a nivel de video", "no prueba predicción anticipada", "Victoria escasa"],
        "class_order": [0, 1, 2],
        "class_names": list(CLASS_NAMES),
        "train_videos": len(train_ids), "validation_videos": len(validation_ids),
        "train_class_counts": counts, "feature_names": feature_names,
        "candidates": {}, "seed": 42,
    }
    for name, class_weight in candidates.items():
        print(f"Entrenando: {name}")
        model = LogisticRegression(max_iter=1000, class_weight=class_weight, random_state=42)
        model.fit(train_x, train_y)
        metrics = evaluate(model, validation_x, validation_y)
        artifact = artifact_dir / f"fusion_{name}.joblib"
        joblib.dump({"model": model, "version": f"experimental-20261001-{name}", "classes": [0, 1, 2], "class_names": list(CLASS_NAMES), "feature_names": feature_names, "class_weight": class_weight, "scaler": None, "encoder": LABELS, "test_used": False, "metrics_validation": metrics}, artifact)
        report["candidates"][name] = {"artifact": str(artifact), "class_weight": class_weight, "metrics_validation": metrics, "hash": sha256(artifact)}
        print(json.dumps({"candidate": name, "macro_f1": metrics["macro_f1"], "balanced_accuracy": metrics["balanced_accuracy"], "recall_Eliminado": metrics["recall"]["Eliminado"]}, ensure_ascii=False))
    report["elapsed_seconds"] = time.perf_counter() - started
    report["source_hashes"] = {"split": sha256(SPLIT)}
    (out / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "config.json").write_text(json.dumps({"version": "experimental-training-20261001", "modalities": MODALITIES, "class_order": [0, 1, 2], "labels": LABELS, "seed": 42, "test_used": False, "scaler": None, "encoder": LABELS}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"split": str(SPLIT), "allowed_splits": ["train", "validation"], "forbidden_split": "test", "source_split_hash": sha256(SPLIT), "status": "CANDIDATO EXPERIMENTAL NO PROMOVIBLE"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ARTEFACTOS: {out}")
    print(f"DURACIÓN: {report['elapsed_seconds']:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
