"""Experimento temporal multimodal usando solo train y validation.

El dataset no tiene timestamp de muerte. Para no inventar una observacion
posterior, el final del clip es un proxy documentado del evento en videos
Eliminado. El artefacto no se activa automaticamente.
"""
from __future__ import annotations

import json
import math
import time
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score,
                             log_loss, precision_recall_fscore_support,
                             roc_auc_score)

ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
SPLIT = ROOT / "backend/data/splits/video_split.csv"
OUT = ROOT / "backend/artifacts/temporal_multimodal_v0.3.0"
REPORT = ROOT / "backend/reports/temporal_v0.3.0"
MODALITIES = ("health", "inventory", "map", "frames", "audio")
CLASSES = (0, 1, 2)
IMAGE_SIZE = (4, 4)
HORIZON = 10.0
WINDOWS = (3.0, 5.0, 8.0, 10.0)


@lru_cache(maxsize=100000)
def feature(path: str) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L").resize(IMAGE_SIZE)
        return np.asarray(image, dtype=np.float32).reshape(-1) / 255.0


def index_rows(frame: pd.DataFrame, time_col: str, path_col: str) -> dict[int, list[tuple[float, str]]]:
    result = {}
    for video_id, group in frame.groupby("id_video"):
        result[int(video_id)] = [(float(row[time_col]), str(row[path_col])) for _, row in group.sort_values(time_col).iterrows()]
    return result


def nearest(items: list[tuple[float, str]], target: float) -> tuple[float, str] | None:
    if not items:
        return None
    prior = [item for item in items if item[0] <= target + 1e-6]
    return prior[-1] if prior else items[0]


def build(ids, labels, durations, data, window):
    rows, y, risk, meta = [], [], [], []
    names = []
    for modality in MODALITIES:
        names += [f"{modality}.current_{i}" for i in range(16)]
        if modality != "audio":
            names += [f"{modality}.delta_{i}" for i in range(16)]
    # Solo se conserva tiempo transcurrido relativo, disponible en inferencia.
    # El tiempo restante al evento sería una fuga futura y no se incluye.
    names += ["time.relative", "time.window_sec"]
    for video_id in ids:
        label = int(labels[video_id])
        # Una observacion cada ~5 s evita tratar recortes consecutivos casi
        # identicos como muestras independientes del mismo video.
        endpoints = data["health"].get(video_id, [])[::4]
        event_time = float(durations[video_id]) if label == 0 else math.inf
        for endpoint, _ in endpoints:
            remaining = event_time - endpoint
            if label == 0 and remaining < -1e-6:
                continue
            values = []
            for modality in MODALITIES:
                selected = nearest(data[modality].get(video_id, []), endpoint)
                width = 16 if modality == "audio" else 32
                if selected is None:
                    values += [0.0] * width
                    continue
                current = feature(selected[1])
                values += current.tolist()
                if modality != "audio":
                    previous = nearest(data[modality].get(video_id, []), max(0.0, endpoint - window))
                    values += (current - (feature(previous[1]) if previous else current)).tolist()
            values += [endpoint / max(float(durations[video_id]), 1e-3), window]
            is_risk = int(label == 0 and 0.0 <= remaining <= HORIZON)
            rows.append(np.asarray(values, dtype=np.float32))
            y.append(label)
            risk.append(is_risk)
            meta.append({"id_video": video_id, "endpoint_sec": endpoint, "remaining_sec": max(remaining, 0.0) if label == 0 else None, "risk_10s": is_risk})
    return np.vstack(rows), np.asarray(y), np.asarray(risk), meta, names


def class_metrics(y, probabilities):
    prediction = np.asarray(CLASSES)[probabilities.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(y, prediction, labels=CLASSES, zero_division=0)
    return {"samples": int(len(y)), "precision": dict(zip(map(str, CLASSES), precision.tolist())), "recall": dict(zip(map(str, CLASSES), recall.tolist())), "f1": dict(zip(map(str, CLASSES), f1.tolist())), "support": dict(zip(map(str, CLASSES), support.tolist())), "f1_macro": float(f1_score(y, prediction, average="macro", zero_division=0)), "balanced_accuracy": float(balanced_accuracy_score(y, prediction)), "log_loss": float(log_loss(y, probabilities, labels=CLASSES)), "confusion_matrix": confusion_matrix(y, prediction, labels=CLASSES).tolist()}


def calibrate(probabilities, y):
    logits = np.log(np.clip(probabilities, 1e-6, 1.0))
    best_t, best_loss = 1.0, float("inf")
    for temperature in np.linspace(0.5, 3.0, 51):
        current = np.exp(logits / temperature)
        current /= current.sum(axis=1, keepdims=True)
        loss = log_loss(y, current, labels=CLASSES)
        if loss < best_loss:
            best_t, best_loss = float(temperature), float(loss)
    current = np.exp(logits / best_t)
    current /= current.sum(axis=1, keepdims=True)
    return best_t, current


def main() -> int:
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(SPLIT, encoding="utf-8-sig")
    eligible = split[split.split.isin(["train", "validation"]) & split.supervised_eligible.astype(bool)]
    labels = dict(zip(eligible.id_video.astype(int), eligible.etiqueta.astype(int)))
    train_ids = eligible.loc[eligible.split == "train", "id_video"].astype(int).tolist()
    validation_ids = eligible.loc[eligible.split == "validation", "id_video"].astype(int).tolist()
    source = {"health": ("df_recortes_vida.csv", "tiempo_seg", "ruta_vida"), "inventory": ("df_recortes_inventario.csv", "tiempo_seg", "ruta_inventario"), "map": ("df_recortes_mapa.csv", "tiempo_seg", "ruta_mapa"), "frames": ("df_frames.csv", "tiempo_seg", "ruta_imagen"), "audio": ("df_audio.csv", "duracion_audio_seg", "ruta_espectrograma")}
    data = {}
    for modality, (filename, time_col, path_col) in source.items():
        data[modality] = index_rows(pd.read_csv(DF_ROOT / filename, encoding="utf-8-sig"), time_col, path_col)
    life = pd.read_csv(DF_ROOT / "df_recortes_vida.csv", encoding="utf-8-sig")
    durations = {int(key): float(value) for key, value in life.groupby("id_video").duracion_video_seg.first().items()}
    report = {"version": "temporal-multimodal-0.3.0", "test_used": False, "horizon_sec": HORIZON, "windows_sec": list(WINDOWS), "class_definition": {"0": "Eliminado/riesgo previo al final del clip", "1": "Eliminacion etiquetada por video", "2": "Victoria etiquetada por video"}, "proxy_event_definition": "duracion_video_seg como limite del evento en videos Eliminado", "class_distribution_videos": eligible.groupby(["split", "clase"]).size().unstack(fill_value=0).to_dict(), "window_results": {}}
    best = None
    for window in WINDOWS:
        x_train, y_train, risk_train, _, names = build(train_ids, labels, durations, data, window)
        x_val, y_val, risk_val, val_meta, _ = build(validation_ids, labels, durations, data, window)
        classifier = SGDClassifier(loss="log_loss", max_iter=35, tol=1e-3, class_weight="balanced", random_state=42)
        risk_model = SGDClassifier(loss="log_loss", max_iter=35, tol=1e-3, class_weight="balanced", random_state=42)
        classifier.fit(x_train, y_train)
        risk_model.fit(x_train, risk_train)
        probabilities = pd.DataFrame(classifier.predict_proba(x_val), columns=classifier.classes_).reindex(columns=CLASSES, fill_value=0.0).to_numpy()
        risk_probability = risk_model.predict_proba(x_val)[:, list(risk_model.classes_).index(1)]
        risk_prediction = (risk_probability >= 0.5).astype(int)
        rp, rr, _, _ = precision_recall_fscore_support(risk_val, risk_prediction, average="binary", zero_division=0)
        risk_metrics = {"precision": float(rp), "recall": float(rr), "f1": float(f1_score(risk_val, risk_prediction, zero_division=0)), "pr_auc": float(average_precision_score(risk_val, risk_probability)), "roc_auc": float(roc_auc_score(risk_val, risk_probability)), "brier": float(brier_score_loss(risk_val, risk_probability))}
        result = {"window_sec": window, "train_windows": int(len(y_train)), "validation_windows": int(len(y_val)), "class": class_metrics(y_val, probabilities), "risk_10s": risk_metrics, "risk_positive_windows": int(risk_val.sum()), "metadata_validation": val_meta}
        report["window_results"][str(window)] = result
        score = result["class"]["f1_macro"] + 0.25 * risk_metrics["recall"] - 0.1 * risk_metrics["brier"]
        if best is None or score > best[0]:
            best = (score, window, classifier, risk_model, names, probabilities, y_val)
    _, window, classifier, risk_model, names, probabilities, y_val = best
    temperature, calibrated = calibrate(probabilities, y_val)
    joblib.dump({"version": "temporal-multimodal-0.3.0", "model": classifier, "risk_model": risk_model, "window_sec": window, "horizon_sec": HORIZON, "feature_names": names, "classes": list(CLASSES), "temperature": temperature, "test_used_for_selection": False, "proxy_event_definition": "duracion_video_seg; no confirma evento real"}, OUT / "temporal_multimodal.joblib")
    report["selected_window_sec"] = window
    report["calibration"] = {"temperature": temperature, "validation_log_loss_before": float(log_loss(y_val, probabilities, labels=CLASSES)), "validation_log_loss_after": float(log_loss(y_val, calibrated, labels=CLASSES))}
    report["selected_artifact"] = str((OUT / "temporal_multimodal.joblib").relative_to(ROOT / "backend"))
    report["elapsed_sec"] = round(time.perf_counter() - started, 3)
    (REPORT / "temporal_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Experimento temporal multimodal v0.3.0", "", "El conjunto `test` no fue leído.", "", f"Ventana seleccionada: **{window} s**", f"Horizonte de riesgo: **{HORIZON} s**", "", "No existe timestamp anotado de eliminación; el final del clip solo se usa como proxy de entrenamiento y no como confirmación en frontend.", "", "| Ventana | Train | Validation | F1 macro | Recall riesgo | PR-AUC | Brier |", "|---:|---:|---:|---:|---:|---:|---:|"]
    for key, item in report["window_results"].items():
        risk = item["risk_10s"]
        lines.append(f"| {key} | {item['train_windows']} | {item['validation_windows']} | {item['class']['f1_macro']:.4f} | {risk['recall']:.4f} | {risk['pr_auc']:.4f} | {risk['brier']:.4f} |")
    lines += ["", f"Artefacto: `{report['selected_artifact']}`", "", "El registry activo no se modificó."]
    (REPORT / "TEMPORAL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"artifact": str(OUT / "temporal_multimodal.joblib"), "report": str(REPORT / "temporal_metrics.json"), "selected_window_sec": window, "test_used": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
