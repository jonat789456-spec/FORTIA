import numpy as np

from app.inference.service import InferenceService


def test_models_load_once_and_predict() -> None:
    service = InferenceService()
    assert {"frames", "health", "inventory", "map", "audio"}.issubset(service.status()["loaded"])
    for modality, model in service.models.items():
        result = service.predict(modality, np.zeros((1, model.n_features_in_), dtype=np.float32))
        assert result["status"] == "ready"
        assert set(result["classProbabilities"]) == {"Eliminado", "Eliminacion", "Victoria"}


def test_fusion_requires_frames() -> None:
    service = InferenceService()
    result = service.fuse({"map": service.predict("map", np.zeros((1, service.models["map"].n_features_in_)))})
    assert result["status"] == "unavailable"


def test_fusion_multimodal_admite_modalidades_faltantes_y_normaliza() -> None:
    service = InferenceService()
    predictions = {"frames": service.predict("frames", np.zeros((1, service.models["frames"].n_features_in_))), "map": service.predict("map", np.zeros((1, service.models["map"].n_features_in_)))}
    result = service.fuse(predictions)
    assert result["status"] == "ready"
    assert result["missingModalities"]
    assert abs(sum(result["classProbabilities"].values()) - 1.0) < 1e-6
    assert result["modelVersion"] == "multimodal-0.1.0"
