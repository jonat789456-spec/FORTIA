from __future__ import annotations

from typing import Mapping


def three_class_to_frontend(probabilities: Mapping[str, float]) -> dict[str, float]:
    """Convierte tres clases internas a la vista binaria existente del frontend.

    `winProbability` significa resultado favorable agrupado; no es una garantía
    de victoria. No se aceptan valores ausentes, negativos ni sumas nulas.
    """
    required = ("Eliminado", "Eliminacion", "Victoria")
    if any(name not in probabilities for name in required):
        raise ValueError("Faltan probabilidades de las tres clases")
    values = {name: float(probabilities[name]) for name in required}
    if any(value < 0 for value in values.values()):
        raise ValueError("Las probabilidades no pueden ser negativas")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("La suma de probabilidades debe ser positiva")
    normalized = {name: value / total for name, value in values.items()}
    return {"winProbability": normalized["Eliminacion"] + normalized["Victoria"], "lossProbability": normalized["Eliminado"]}

