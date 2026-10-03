from pathlib import Path

from app.collection.failure_recorder import FailureRecorder
from app.inference.risk import RiskPoint, TemporalRiskFeatures, safety_signal


def test_tendencias_no_inventan_lecturas_desconocidas() -> None:
    tracker = TemporalRiskFeatures()
    first = tracker.add(RiskPoint(0.0, health=None, shield=80.0))
    second = tracker.add(RiskPoint(1.0, health=20.0, shield=60.0))
    assert first["health.current"] is None
    assert second["health.delta.1s"] is None
    assert second["shield.delta.1s"] == -20.0


def test_regla_de_seguridad_es_separada_de_la_probabilidad() -> None:
    signal = safety_signal({"health.current": 15.0, "health.delta.1s": -20.0, "storm": None})
    assert signal["active"] is True
    assert signal["source"] == "regla_seguridad"
    assert signal["not_model_probability"] is True


def test_recorder_es_opt_in_y_deduplica(tmp_path: Path) -> None:
    disabled = FailureRecorder(tmp_path / "disabled")
    assert disabled.record_case({"sessionId": "s", "result": "Eliminado"}) is False
    recorder = FailureRecorder(tmp_path / "enabled", enabled=True, max_cases=2)
    case = {"sessionId": "s", "result": "Eliminado", "timestamp": 1, "eventType": "late"}
    assert recorder.record_case(case, [b"frame"] * 6) is True
    assert recorder.record_case(case, [b"frame"] * 6) is False
    assert len(list((tmp_path / "enabled" / "frames").rglob("*.jpg"))) == 6
