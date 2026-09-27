from app.model_registry import registry


def test_registry_has_expected_modalities() -> None:
    models = registry.load()["models"]
    assert {"frames", "health", "inventory", "map", "audio", "fusion"}.issubset(models)


def test_baselines_expose_reproducible_metadata() -> None:
    models = registry.load()["models"]
    for name in ("frames", "health", "inventory", "map", "audio"):
        item = models[name]
        assert item["classes"] == [0, 1, 2]
        assert item["input_features"] > 0
        assert item["input_shape"]
        assert item["normalization"]
        assert item["scaler"] is None
        assert item["selection_split"] == "validation"
        assert item["test_used_for_selection"] is False
        assert set(item["validation"]) >= {"f1_macro", "balanced_accuracy", "log_loss"}
