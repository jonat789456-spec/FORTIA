"""Evalúa una fusión tardía simple de probabilidades en validation."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss

from train_baselines import aggregate_rows


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = ROOT / "backend" / "data" / "splits" / "video_split.csv"
ARTIFACTS = ROOT / "backend" / "artifacts" / "baselines"
REPORTS = ROOT / "backend" / "reports" / "baselines"


def main() -> int:
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    validation_ids = split.loc[split.split == "validation", "id_video"].tolist()
    labels = dict(zip(split.id_video, split.etiqueta))
    datasets = {
        "frames": ("df_frames.csv", "ruta_imagen", True),
        "health": ("df_recortes_vida.csv", "ruta_vida", False),
        "inventory": ("df_recortes_inventario.csv", "ruta_inventario", False),
        "map": ("df_recortes_mapa.csv", "ruta_mapa", False),
        "audio": ("df_audio.csv", "ruta_espectrograma", False),
    }
    probabilities: list[np.ndarray] = []
    modalities = []
    for name, (csv_name, path_column, sequence) in datasets.items():
        frame = pd.read_csv(DF_ROOT / csv_name, encoding="utf-8-sig")
        features, ids = aggregate_rows(frame, path_column, validation_ids, sequence)
        model = joblib.load(ARTIFACTS / f"{name}_logistic.joblib")["model"]
        current = pd.DataFrame(model.predict_proba(features), index=ids, columns=model.classes_)
        current = current.reindex(columns=[0, 1, 2], fill_value=0.0).reindex(validation_ids)
        probabilities.append(current.to_numpy())
        modalities.append(name)
    fused = np.mean(probabilities, axis=0)
    fused = fused / fused.sum(axis=1, keepdims=True)
    y_true = np.asarray([labels[int(value)] for value in validation_ids])
    y_pred = fused.argmax(axis=1)
    metrics = {
        "samples": int(len(y_true)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "log_loss": float(log_loss(y_true, fused, labels=[0, 1, 2])),
    }
    result = {"method": "equal_probability_average", "weights": {name: 1 / len(modalities) for name in modalities}, "modalities": modalities, "validation": metrics, "test_used": False}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "fusion_baseline.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (REPORTS / "FUSION_REPORT.md").write_text("# Baseline de fusión\n\n" + json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
