"""Entrena baselines ligeros por modalidad sin consultar el conjunto de prueba."""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = ROOT / "backend" / "data" / "splits" / "video_split.csv"
ARTIFACTS = ROOT / "backend" / "artifacts" / "baselines"
REPORTS = ROOT / "backend" / "reports" / "baselines"
IMAGE_SIZE = (16, 16)


def image_feature(path: str) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB").resize(IMAGE_SIZE)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return array.reshape(-1)


def aggregate_rows(frame: pd.DataFrame, path_column: str, video_ids: list[int], sequence: bool = False) -> tuple[np.ndarray, np.ndarray]:
    grouped = frame.sort_values(["id_video", frame.columns[1]]).groupby("id_video")
    features: list[np.ndarray] = []
    ids: list[int] = []
    for video_id in video_ids:
        if video_id not in grouped.groups:
            continue
        rows = grouped.get_group(video_id)
        vectors = [image_feature(path) for path in rows[path_column].tolist()]
        if sequence:
            vectors = vectors[:6]
            vectors.extend([np.zeros_like(vectors[0])] * (6 - len(vectors)))
            vector = np.concatenate(vectors)
        else:
            matrix = np.vstack(vectors)
            vector = np.concatenate([matrix.mean(axis=0), matrix.std(axis=0)])
        features.append(vector)
        ids.append(video_id)
    return np.vstack(features), np.asarray(ids, dtype=np.int64)


def evaluate(model: LogisticRegression, x: np.ndarray, y: np.ndarray) -> dict[str, float | int]:
    probabilities = model.predict_proba(x)
    predicted = model.classes_[probabilities.argmax(axis=1)]
    return {
        "samples": int(len(y)),
        "f1_macro": float(f1_score(y, predicted, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "log_loss": float(log_loss(y, probabilities, labels=[0, 1, 2])),
    }


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    labels = dict(zip(split.id_video, split.etiqueta))
    train_ids = split.loc[split.split == "train", "id_video"].tolist()
    validation_ids = split.loc[split.split == "validation", "id_video"].tolist()
    datasets = {
        "frames": (pd.read_csv(DF_ROOT / "df_frames.csv", encoding="utf-8-sig"), "ruta_imagen", True),
        "health": (pd.read_csv(DF_ROOT / "df_recortes_vida.csv", encoding="utf-8-sig"), "ruta_vida", False),
        "inventory": (pd.read_csv(DF_ROOT / "df_recortes_inventario.csv", encoding="utf-8-sig"), "ruta_inventario", False),
        "map": (pd.read_csv(DF_ROOT / "df_recortes_mapa.csv", encoding="utf-8-sig"), "ruta_mapa", False),
        "audio": (pd.read_csv(DF_ROOT / "df_audio.csv", encoding="utf-8-sig"), "ruta_espectrograma", False),
    }
    results: dict[str, object] = {"image_size": IMAGE_SIZE, "selection_split": "validation", "test_used": False, "modalities": {}}
    for name, (frame, path_column, sequence) in datasets.items():
        started = time.perf_counter()
        train_x, train_order = aggregate_rows(frame, path_column, train_ids, sequence)
        validation_x, validation_order = aggregate_rows(frame, path_column, validation_ids, sequence)
        train_y = np.asarray([labels[int(value)] for value in train_order])
        validation_y = np.asarray([labels[int(value)] for value in validation_order])
        model = LogisticRegression(max_iter=500, class_weight="balanced", random_state=42)
        model.fit(train_x, train_y)
        validation_metrics = evaluate(model, validation_x, validation_y)
        artifact = ARTIFACTS / f"{name}_logistic.joblib"
        feature_shape = list(train_x.shape[1:])
        joblib.dump(
            {
                "model": model,
                "image_size": list(IMAGE_SIZE),
                "classes": [0, 1, 2],
                "modality": name,
                "version": "baseline-0.2.0",
                "input_features": int(train_x.shape[1]),
                "input_shape": feature_shape,
                "normalization": "RGB convert, resize 16x16, float32 / 255.0; aggregate mean/std except frames",
                "scaler": None,
                "selection_split": "validation",
                "test_used_for_selection": False,
                "validation_metrics": validation_metrics,
            },
            artifact,
        )
        results["modalities"][name] = {
            "algorithm": "LogisticRegression",
            "train_samples": int(len(train_y)),
            "validation_samples": int(len(validation_y)),
            "validation": validation_metrics,
            "artifact": str(artifact.relative_to(ROOT / "backend")),
            "elapsed_sec": round(time.perf_counter() - started, 3),
        }
        print(json.dumps({"modality": name, "validation": validation_metrics}, ensure_ascii=False))
    (REPORTS / "baseline_metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ["# Baselines", "", "Los modelos se ajustaron únicamente con `train` y se compararon en `validation`.", "", "| Modalidad | F1 macro | Balanced accuracy | Log loss |", "|---|---:|---:|---:|"]
    for name, values in results["modalities"].items():
        metrics = values["validation"]
        report.append(f"| {name} | {metrics['f1_macro']:.4f} | {metrics['balanced_accuracy']:.4f} | {metrics['log_loss']:.4f} |")
    report.extend(["", "El conjunto `test` no se utilizó.", "", "Las características son baselines de imagen reducida; no representan todavía modelos finales."])
    (REPORTS / "BASELINE_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
