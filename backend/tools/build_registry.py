"""Construye el registro central a partir de artefactos y métricas de validación."""

from __future__ import annotations

import json
from pathlib import Path

import joblib


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
ARTIFACTS = BACKEND / "artifacts" / "baselines"
METRICS = BACKEND / "reports" / "baselines" / "baseline_metrics.json"
REGISTRY = BACKEND / "artifacts" / "registry.json"


def main() -> int:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    models: dict[str, object] = {}
    for name, values in metrics["modalities"].items():
        artifact_path = ARTIFACTS / f"{name}_logistic.joblib"
        payload = joblib.load(artifact_path)
        models[name] = {
            "version": payload["version"],
            "artifact": str(artifact_path.relative_to(BACKEND)).replace("\\", "/"),
            "status": "validated_on_validation",
            "algorithm": "LogisticRegression",
            "classes": payload["classes"],
            "input_shape": payload["input_shape"],
            "input_features": payload["input_features"],
            "image_size": payload["image_size"],
            "normalization": payload["normalization"],
            "scaler": payload["scaler"],
            "selection_split": payload["selection_split"],
            "test_used_for_selection": payload["test_used_for_selection"],
            "validation": values["validation"],
        }
    multimodal_artifact = BACKEND / "artifacts" / "multimodal" / "fusion_model.joblib"
    if multimodal_artifact.exists():
        payload = joblib.load(multimodal_artifact)
        models["fusion"] = {
            "version": payload["version"], "artifact": str(multimodal_artifact.relative_to(BACKEND)).replace("\\", "/"),
            "status": "validated_on_validation", "classes": payload["classes"], "feature_names": payload["feature_names"],
            "required_modality": payload["required_modality"], "mask_semantics": payload["mask_semantics"],
            "selection_split": "validation", "test_used_for_selection": False, "validation": payload["validation_metrics"],
        }
    else:
        models["fusion"] = {"version": "baseline-0.1.0", "artifact": "reports/baselines/fusion_baseline.json", "status": "validated_on_validation", "selection_split": "validation", "test_used_for_selection": False, "validation": json.loads((BACKEND / "reports" / "baselines" / "fusion_baseline.json").read_text(encoding="utf-8"))}
    REGISTRY.write_text(json.dumps({"registryVersion": "1.1", "generatedBy": "build_registry.py", "models": models, "testUsedForSelection": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"registry": str(REGISTRY), "models": list(models)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
