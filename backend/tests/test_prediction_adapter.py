import pytest

from app.prediction_adapter import three_class_to_frontend


def test_three_class_conversion() -> None:
    result = three_class_to_frontend({"Eliminado": 0.2, "Eliminacion": 0.5, "Victoria": 0.3})
    assert result == {"winProbability": 0.8, "lossProbability": 0.2}


def test_three_class_conversion_rejects_missing_class() -> None:
    with pytest.raises(ValueError):
        three_class_to_frontend({"Eliminado": 1.0})

