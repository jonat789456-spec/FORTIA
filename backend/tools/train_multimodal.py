"""Entrena y compara fusiones pequeñas usando solo train/validation.

El conjunto test no se lee en este script.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_recall_fscore_support

from tools.train_baselines import aggregate_rows


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = ROOT / "backend" / "data" / "splits" / "video_split.csv"
ARTIFACTS = ROOT / "backend" / "artifacts" / "multimodal"
REPORTS = ROOT / "backend" / "reports" / "multimodal"
MODALITIES = ("frames", "health", "inventory", "map", "audio")
CLASS_NAMES = ("Eliminado", "Eliminacion", "Victoria")


def build_features(ids: list[int], labels: dict[int, int], artifact_models: dict[str, object], datasets: dict[str, tuple[pd.DataFrame, str, bool]]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    rows: list[list[float]] = []
    targets: list[int] = []
    names = [f"{modality}.p_{name}" for modality in MODALITIES for name in CLASS_NAMES] + [f"available.{modality}" for modality in MODALITIES]
    grouped_features: dict[str, dict[int, np.ndarray]] = {}
    for modality in MODALITIES:
        frame, path_column, sequence = datasets[modality]
        features, feature_ids = aggregate_rows(frame, path_column, ids, sequence)
        probabilities = artifact_models[modality].predict_proba(features)
        grouped_features[modality] = {int(video_id): probabilities[index] for index, video_id in enumerate(feature_ids)}
    for video_id in ids:
        values: list[float] = []
        available: list[float] = []
        for modality in MODALITIES:
            probability = grouped_features[modality].get(int(video_id))
            if probability is None:
                values.extend([0.0, 0.0, 0.0])
                available.append(0.0)
            else:
                values.extend([float(item) for item in probability])
                available.append(1.0)
        rows.append(values + available)
        targets.append(int(labels[int(video_id)]))
    return np.asarray(rows, dtype=np.float32), np.asarray(targets, dtype=np.int64), names


def metrics(model: object, features: np.ndarray, target: np.ndarray) -> dict[str, object]:
    started = time.perf_counter()
    probabilities = model.predict_proba(features)
    latency = (time.perf_counter() - started) * 1000 / max(1, len(target))
    predicted = np.asarray(model.classes_)[probabilities.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(target, predicted, labels=[0, 1, 2], zero_division=0)
    return {
        "samples": int(len(target)),
        "precision": dict(zip(CLASS_NAMES, precision.astype(float))),
        "recall": dict(zip(CLASS_NAMES, recall.astype(float))),
        "f1": dict(zip(CLASS_NAMES, f1.astype(float))),
        "support": dict(zip(CLASS_NAMES, [int(value) for value in support])),
        "f1_macro": float(f1_score(target, predicted, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(target, predicted, average="weighted", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(target, predicted)),
        "log_loss": float(log_loss(target, probabilities, labels=[0, 1, 2])),
        "confusion_matrix": confusion_matrix(target, predicted, labels=[0, 1, 2]).tolist(),
        "mean_latency_ms": float(latency),
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    usable = split[split["split"].isin(["train", "validation"])]
    label_codes = {"Eliminado": 0, "Eliminacion": 1, "Victoria": 2}
    labels = {int(row.id_video): label_codes[str(row.clase)] for row in usable.itertuples()}
    datasets = {
        "frames": (pd.read_csv(DF_ROOT / "df_frames.csv", encoding="utf-8-sig"), "ruta_imagen", True),
        "health": (pd.read_csv(DF_ROOT / "df_recortes_vida.csv", encoding="utf-8-sig"), "ruta_vida", False),
        "inventory": (pd.read_csv(DF_ROOT / "df_recortes_inventario.csv", encoding="utf-8-sig"), "ruta_inventario", False),
        "map": (pd.read_csv(DF_ROOT / "df_recortes_mapa.csv", encoding="utf-8-sig"), "ruta_mapa", False),
        "audio": (pd.read_csv(DF_ROOT / "df_audio.csv", encoding="utf-8-sig"), "ruta_espectrograma", False),
    }
    artifact_models = {modality: joblib.load(ROOT / "backend" / "artifacts" / "baselines" / f"{modality}_logistic.joblib")["model"] for modality in MODALITIES}
    train_ids = [int(value) for value in split.loc[split.split == "train", "id_video"]]
    validation_ids = [int(value) for value in split.loc[split.split == "validation", "id_video"]]
    train_x, train_y, feature_names = build_features(train_ids, labels, artifact_models, datasets)
    validation_x, validation_y, _ = build_features(validation_ids, labels, artifact_models, datasets)
    candidates: dict[str, object] = {
        "logistic": LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
        "gradient_boosting": HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, max_leaf_nodes=7, l2_regularization=1.0, random_state=42),
    }
    report: dict[str, object] = {"test_used": False, "train_samples": len(train_y), "validation_samples": len(validation_y), "feature_names": feature_names, "candidates": {}, "ablations": {}}
    for name, model in candidates.items():
        model.fit(train_x, train_y)
        report["candidates"][name] = metrics(model, validation_x, validation_y)
    equal = validation_x[:, :15].reshape(-1, 5, 3).mean(axis=1)
    equal /= equal.sum(axis=1, keepdims=True)
    equal_pred = np.argmax(equal, axis=1)
    report["candidates"]["weighted_average"] = {"f1_macro": float(f1_score(validation_y, equal_pred, average="macro", zero_division=0)), "balanced_accuracy": float(balanced_accuracy_score(validation_y, equal_pred)), "log_loss": float(log_loss(validation_y, equal, labels=[0, 1, 2])), "confusion_matrix": confusion_matrix(validation_y, equal_pred, labels=[0, 1, 2]).tolist(), "mean_latency_ms": 0.0}
    selected_name = max(("logistic", "gradient_boosting", "weighted_average"), key=lambda name: (report["candidates"][name]["f1_macro"], -report["candidates"][name]["log_loss"]))
    if selected_name == "weighted_average":
        selected = {"method": "weighted_average", "weights": {modality: 0.2 for modality in MODALITIES}}
    else:
        selected = candidates[selected_name]
        joblib.dump({"model": selected, "version": "multimodal-0.1.0", "classes": [0, 1, 2], "feature_names": feature_names, "required_modality": "frames", "mask_semantics": "1 available, 0 unavailable; missing probability vectors are zeros", "test_used_for_selection": False, "validation_metrics": report["candidates"][selected_name]}, ARTIFACTS / "fusion_model.joblib")
    report["selected"] = selected_name
    for removed in MODALITIES:
        ablation_x = validation_x.copy()
        start = MODALITIES.index(removed) * 3
        ablation_x[:, start:start + 3] = 0.0
        ablation_x[:, 15 + MODALITIES.index(removed)] = 0.0
        if selected_name == "weighted_average":
            probabilities = ablation_x[:, :15].reshape(-1, 5, 3).mean(axis=1)
            sums = probabilities.sum(axis=1, keepdims=True)
            probabilities = np.divide(probabilities, sums, out=np.zeros_like(probabilities), where=sums != 0)
            predicted = probabilities.argmax(axis=1)
            report["ablations"][removed] = {"f1_macro": float(f1_score(validation_y, predicted, average="macro", zero_division=0)), "balanced_accuracy": float(balanced_accuracy_score(validation_y, predicted)), "log_loss": float(log_loss(validation_y, probabilities, labels=[0, 1, 2]))}
        else:
            report["ablations"][removed] = metrics(selected, ablation_x, validation_y)
    (REPORTS / "MULTIMODAL_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORTS / "MULTIMODAL_REPORT.md").write_text("# Modelo multimodal\n\nSelección únicamente con `train` y `validation`; `test` no utilizado.\n\nModelo seleccionado: **" + selected_name + "**.\n\nConsultar `MULTIMODAL_REPORT.json` para métricas por clase, matriz de confusión y ablaciones.\n", encoding="utf-8")
    print(json.dumps({"selected": selected_name, "validation": report["candidates"][selected_name], "test_used": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
