"""Compara fusiones con pesos moderados usando solo train/validation.

No lee features ni imágenes del split test y nunca sobrescribe el artefacto activo.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_recall_fscore_support

from app.class_mapping import CLASS_NAMES
from tools.train_multimodal import build_features

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = BACKEND / "data" / "splits" / "video_split.csv"
OUT_ARTIFACTS = BACKEND / "artifacts" / "fusion_candidates_20261001"
OUT_REPORT = BACKEND / "reports" / "fusion_candidates_20261001"
MODALITIES = ("frames", "health", "inventory", "map", "audio")


def metrics(model: LogisticRegression, x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    probabilities = model.predict_proba(x)
    predicted = model.classes_[probabilities.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(y, predicted, labels=[0, 1, 2], zero_division=0)
    brier = float(np.mean(np.sum((probabilities - np.eye(3)[y]) ** 2, axis=1)))
    return {"samples": int(len(y)), "precision": dict(zip(CLASS_NAMES, precision.tolist())), "recall": dict(zip(CLASS_NAMES, recall.tolist())), "f1": dict(zip(CLASS_NAMES, f1.tolist())), "support": dict(zip(CLASS_NAMES, support.tolist())), "macroF1": float(f1_score(y, predicted, average="macro", zero_division=0)), "balancedAccuracy": float(balanced_accuracy_score(y, predicted)), "logLoss": float(log_loss(y, probabilities, labels=[0, 1, 2])), "brierMulticlass": brier, "confusionMatrix": confusion_matrix(y, predicted, labels=[0, 1, 2]).tolist(), "predictionDistribution": {CLASS_NAMES[index]: int((predicted == index).sum()) for index in range(3)}, "meanConfidence": float(probabilities.max(axis=1).mean())}


def calibration(probabilities: np.ndarray, y: np.ndarray) -> dict[str, float]:
    best_temperature = 1.0
    best_loss = log_loss(y, probabilities, labels=[0, 1, 2])
    for temperature in np.linspace(0.5, 3.0, 51):
        scaled = np.power(np.clip(probabilities, 1e-8, 1.0), 1.0 / temperature)
        scaled /= scaled.sum(axis=1, keepdims=True)
        loss = log_loss(y, scaled, labels=[0, 1, 2])
        if loss < best_loss:
            best_temperature, best_loss = float(temperature), float(loss)
    scaled = np.power(np.clip(probabilities, 1e-8, 1.0), 1.0 / best_temperature)
    scaled /= scaled.sum(axis=1, keepdims=True)
    return {"temperature": best_temperature, "logLossBefore": float(log_loss(y, probabilities, labels=[0, 1, 2])), "logLossAfter": float(best_loss), "brierBefore": float(np.mean(np.sum((probabilities - np.eye(3)[y]) ** 2, axis=1))), "brierAfter": float(np.mean(np.sum((scaled - np.eye(3)[y]) ** 2, axis=1)))}


def normalized_weights(counts: dict[str, int], mode: str) -> dict[int, float] | None:
    if mode == "none":
        return None
    raw = {name: (1.0 / np.sqrt(count) if mode == "sqrt_inverse" else 496.0 / (3.0 * count)) for name, count in counts.items()}
    if mode == "capped_balanced":
        raw = {name: min(value, 3.0) for name, value in raw.items()}
    mean = sum(raw.values()) / len(raw)
    return {index: value / mean for index, (name, value) in enumerate(raw.items())}


def main() -> int:
    started = time.perf_counter()
    OUT_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    usable = split[split["split"].isin(["train", "validation"])]
    labels = {int(row.id_video): {"Eliminado": 0, "Eliminacion": 1, "Victoria": 2}[str(row.clase)] for row in usable.itertuples()}
    datasets = {"frames": (pd.read_csv(DF_ROOT / "df_frames.csv", encoding="utf-8-sig"), "ruta_imagen", True), "health": (pd.read_csv(DF_ROOT / "df_recortes_vida.csv", encoding="utf-8-sig"), "ruta_vida", False), "inventory": (pd.read_csv(DF_ROOT / "df_recortes_inventario.csv", encoding="utf-8-sig"), "ruta_inventario", False), "map": (pd.read_csv(DF_ROOT / "df_recortes_mapa.csv", encoding="utf-8-sig"), "ruta_mapa", False), "audio": (pd.read_csv(DF_ROOT / "df_audio.csv", encoding="utf-8-sig"), "ruta_espectrograma", False)}
    models = {modality: joblib.load(BACKEND / "artifacts" / "baselines" / f"{modality}_logistic.joblib")["model"] for modality in MODALITIES}
    train_ids = [int(value) for value in split.loc[split["split"] == "train", "id_video"]]
    validation_ids = [int(value) for value in split.loc[split["split"] == "validation", "id_video"]]
    train_x, train_y, feature_names = build_features(train_ids, labels, models, datasets)
    validation_x, validation_y, _ = build_features(validation_ids, labels, models, datasets)
    np.savez_compressed(OUT_REPORT / "validation_features.npz", features=validation_x, labels=validation_y)
    counts = {name: int((train_y == index).sum()) for index, name in enumerate(CLASS_NAMES)}
    candidates = {"none": None, "sqrt_inverse": normalized_weights(counts, "sqrt_inverse"), "capped_balanced": normalized_weights(counts, "capped_balanced"), "balanced_reference": normalized_weights(counts, "balanced")}
    report: dict[str, object] = {"testUsed": False, "trainVideos": len(train_ids), "validationVideos": len(validation_ids), "classCounts": counts, "candidates": {}, "featureNames": feature_names, "visualReview": "Victoria y Eliminado tienen overlays posteriores visibles; no se usan como evidencia de riesgo previo."}
    for name, class_weight in candidates.items():
        model = LogisticRegression(max_iter=1000, class_weight=class_weight, random_state=42)
        model.fit(train_x, train_y)
        result = metrics(model, validation_x, validation_y)
        probabilities = model.predict_proba(validation_x)
        result["calibrationValidationOnly"] = calibration(probabilities, validation_y)
        probe = np.zeros((1, train_x.shape[1]), dtype=np.float32)
        latencies = []
        for _ in range(100):
            t0 = time.perf_counter(); model.predict_proba(probe); latencies.append((time.perf_counter() - t0) * 1000)
        result["latencyMs"] = {"mean": float(np.mean(latencies)), "p95": float(np.percentile(latencies, 95))}
        artifact = OUT_ARTIFACTS / f"fusion_{name}.joblib"
        joblib.dump({"model": model, "version": f"fusion-candidate-20261001-{name}", "classes": [0, 1, 2], "class_names": list(CLASS_NAMES), "class_weight": class_weight, "feature_names": feature_names, "selection_split": "validation", "test_used_for_selection": False, "validation_metrics": result}, artifact)
        report["candidates"][name] = {"classWeight": class_weight, "artifact": str(artifact), "metrics": result}
    report["elapsedSec"] = time.perf_counter() - started
    (OUT_REPORT / "FUSION_CANDIDATES_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(OUT_REPORT / "FUSION_CANDIDATES_REPORT.json"), "candidates": list(candidates), "testUsed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
