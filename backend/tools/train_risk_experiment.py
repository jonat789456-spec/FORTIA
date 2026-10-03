"""Entrena la versión experimental con ventanas anotadas y sin tocar test.

El CSV debe contener ``id_video``, ``split`` (train/validation),
``risk_label``, ``confirmed_label`` y columnas numéricas de características.
Las columnas con ``split=test`` provocan un error deliberado.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score,
                             precision_recall_fscore_support)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]


def metrics(y: np.ndarray, probability: np.ndarray, labels: list[int]) -> dict[str, object]:
    prediction = np.asarray(labels)[probability.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(y, prediction, labels=labels, zero_division=0)
    eliminated = probability[:, labels.index(0)]
    return {
        "samples": int(len(y)),
        "precision": dict(zip(map(str, labels), precision.tolist())),
        "recall": dict(zip(map(str, labels), recall.tolist())),
        "f1": dict(zip(map(str, labels), f1.tolist())),
        "support": dict(zip(map(str, labels), support.tolist())),
        "f1_macro": float(f1_score(y, prediction, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, prediction)),
        "confusion_matrix": confusion_matrix(y, prediction, labels=labels).tolist(),
        "pr_auc_eliminado": float(average_precision_score((y == 0).astype(int), eliminated)),
        "brier_eliminado": float(brier_score_loss((y == 0).astype(int), eliminated)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "backend/artifacts/risk_experiment_v1")
    parser.add_argument("--report", type=Path, default=ROOT / "backend/reports/risk_experiment_v1")
    args = parser.parse_args()
    started = time.perf_counter()
    frame = pd.read_csv(args.input)
    if "test" in set(frame.get("split", pd.Series(dtype=str)).astype(str).str.casefold()):
        raise ValueError("El conjunto test está sellado: retíralo antes de entrenar.")
    required = {"id_video", "split", "main_label", "risk_3s", "risk_5s", "risk_10s"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Faltan columnas: {sorted(missing)}")
    train = frame[frame.split == "train"].copy()
    validation = frame[frame.split == "validation"].copy()
    if train.empty or validation.empty:
        raise ValueError("Se requieren filas train y validation.")
    excluded = {"id_video", "split", "main_label", "risk_3s", "risk_5s", "risk_10s", "window", "seconds_to_event", "outcome", "session_id"}
    feature_names = [column for column in frame.columns if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])]
    if not feature_names:
        raise ValueError("No hay características numéricas temporales.")
    x_train = train[feature_names].replace([np.inf, -np.inf], np.nan).fillna(train[feature_names].median(numeric_only=True)).fillna(0.0)
    x_val = validation[feature_names].replace([np.inf, -np.inf], np.nan).fillna(x_train.median()).fillna(0.0)
    y_train = train.main_label.to_numpy(dtype=int)
    y_val = validation.main_label.to_numpy(dtype=int)
    main_model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight="balanced", random_state=42))
    risk_models: dict[str, object] = {}
    main_model.fit(x_train, y_train)
    for horizon in (3, 5, 10):
        target = train[f"risk_{horizon}s"].to_numpy(dtype=int)
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight="balanced", random_state=42))
        model.fit(x_train, target)
        risk_models[str(horizon)] = model
    main_prob = main_model.predict_proba(x_val)
    if list(main_model.classes_) != [0, 1, 2]:
        aligned = np.zeros((len(x_val), 3), dtype=float)
        for index, label in enumerate(main_model.classes_):
            aligned[:, int(label)] = main_prob[:, index]
        main_prob = aligned
    result = {
        "version": "risk-experiment-v1",
        "test_used": False,
        "selection_split": "validation",
        "feature_names": feature_names,
        "train_videos": int(train.id_video.nunique()),
        "validation_videos": int(validation.id_video.nunique()),
        "train_windows": int(len(train)),
        "validation_windows": int(len(validation)),
        "main_metrics": metrics(y_val, main_prob, [0, 1, 2]),
        "risk_horizons": {horizon: {"positive_windows": int(validation[f"risk_{horizon}s"].sum())} for horizon in ("3", "5", "10")},
        "class_distribution": frame.groupby(["split", "main_label"]).size().unstack(fill_value=0).to_dict(),
        "latency_note": "medir con benchmark de inferencia antes de activación",
        "elapsed_sec": round(time.perf_counter() - started, 3),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    args.report.mkdir(parents=True, exist_ok=True)
    joblib.dump({"version": result["version"], "model": main_model, "risk_models": risk_models, "feature_names": feature_names, "classes": [0, 1, 2], "test_used_for_selection": False}, args.output / "risk_multimodal.joblib")
    (args.report / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.report / "REPORT.md").write_text("# Experimento de riesgo v1\n\n`test` no fue utilizado.\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps({"artifact": str(args.output / "risk_multimodal.joblib"), "report": str(args.report / "metrics.json"), "test_used": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
