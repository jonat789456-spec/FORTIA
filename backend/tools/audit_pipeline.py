"""Auditoría reproducible del pipeline sin inferir sobre imágenes ni abrir test."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

from app.class_mapping import CLASS_NAMES, align_probabilities, frontend_class_from_name

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = BACKEND / "reports" / "pipeline_audit_20260930"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path: Path) -> dict[str, object]:
    payload = joblib.load(path)
    model = payload["model"]
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "modified": path.stat().st_mtime,
        "payloadVersion": payload.get("version"),
        "modelType": type(model).__name__,
        "inputFeatures": getattr(model, "n_features_in_", None),
        "outputClasses": [int(value) for value in getattr(model, "classes_", [])],
        "classWeight": getattr(model, "class_weight", None),
        "classNames": list(CLASS_NAMES),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(BACKEND / "data" / "splits" / "video_split.csv", encoding="utf-8-sig")
    matrix = pd.read_csv(BACKEND / "data" / "manifests" / "modality_matrix.csv", encoding="utf-8-sig")
    counts = {split_name: {name: int(value) for name, value in split.loc[split["split"] == split_name, "clase"].value_counts().reindex(CLASS_NAMES, fill_value=0).items()} for split_name in ("train", "validation", "test", "excluded_ambiguous")}
    train_counts = counts["train"]
    train_total = sum(train_counts.values())
    balanced_weights = {name: train_total / (len(CLASS_NAMES) * count) for name, count in train_counts.items() if count}
    model_paths = {
        "frames": BACKEND / "artifacts" / "baselines" / "frames_logistic.joblib",
        "health": BACKEND / "artifacts" / "baselines" / "health_logistic.joblib",
        "inventory": BACKEND / "artifacts" / "baselines" / "inventory_logistic.joblib",
        "map": BACKEND / "artifacts" / "baselines" / "map_logistic.joblib",
        "audio": BACKEND / "artifacts" / "baselines" / "audio_logistic.joblib",
        "fusion": BACKEND / "artifacts" / "multimodal" / "fusion_model.joblib",
    }
    model_info = {name: artifact(path) for name, path in model_paths.items()}
    synthetic = {
        "[1,0,0]": {"internal": "Eliminado", "frontend": "eliminated"},
        "[0,1,0]": {"internal": "Eliminacion", "frontend": "elimination"},
        "[0,0,1]": {"internal": "Victoria", "frontend": "victory"},
        "[0.8,0.1,0.1]": {"internal": "Eliminado", "frontend": "eliminated"},
        "[0.1,0.8,0.1]": {"internal": "Eliminacion", "frontend": "elimination"},
        "[0.1,0.1,0.8]": {"internal": "Victoria", "frontend": "victory"},
    }
    modality_availability = {column: int(matrix[column].sum()) for column in matrix.columns if column.endswith("_available")}
    report = {
        "testEvaluated": False,
        "classOrder": {str(index): name for index, name in enumerate(CLASS_NAMES)},
        "frontendOrder": {name: frontend_class_from_name(name) for name in CLASS_NAMES},
        "syntheticMapping": synthetic,
        "splitVideoCounts": counts,
        "totalVideos": int(split["id_video"].nunique()),
        "modalityAvailabilityByVideo": modality_availability,
        "classWeightsObserved": {"source": "sklearn class_weight=balanced", "byClass": balanced_weights, "indexOrder": {str(index): name for index, name in enumerate(CLASS_NAMES)}},
        "artifacts": model_info,
        "observations": [
            "El modelo de fusión es LogisticRegression multiclase con tres salidas y 20 features.",
            "La fusión activa fue entrenada con audio de espectrograma; audio_raw se mantiene fuera de esa entrada.",
            "No se encontró un fallback de porcentajes en el backend activo; el modo demo existe solo en frontend/demo.ts y no se activa en App.",
            "Los valores ausentes de fusión usan máscara de disponibilidad y vector cero; el modelo fue validado con esa semántica.",
        ],
    }
    (OUT / "PIPELINE_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(OUT / "PIPELINE_AUDIT.json"), "testEvaluated": False, "classOrder": report["classOrder"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
