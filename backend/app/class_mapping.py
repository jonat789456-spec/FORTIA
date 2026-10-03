from __future__ import annotations

from collections.abc import Mapping

CLASS_NAMES: tuple[str, str, str] = ("Eliminado", "Eliminacion", "Victoria")
CLASS_CODES: dict[str, int] = {name: index for index, name in enumerate(CLASS_NAMES)}
FRONTEND_CLASS_NAMES: dict[str, str] = {
    "Eliminado": "eliminated",
    "Eliminacion": "elimination",
    "Victoria": "victory",
}


def class_name_from_code(code: int) -> str:
    if code not in range(len(CLASS_NAMES)):
        raise ValueError(f"Código de clase incompatible: {code}")
    return CLASS_NAMES[code]


def frontend_class_from_name(name: str) -> str:
    try:
        return FRONTEND_CLASS_NAMES[name]
    except KeyError as exc:
        raise ValueError(f"Clase interna desconocida: {name}") from exc


def align_probabilities(labels: list[int] | tuple[int, ...], values: list[float] | tuple[float, ...]) -> dict[str, float]:
    if len(labels) != len(values) or set(labels) != set(range(len(CLASS_NAMES))):
        raise ValueError(f"La salida debe contener exactamente los códigos {list(range(len(CLASS_NAMES)))}")
    result = {name: 0.0 for name in CLASS_NAMES}
    for label, value in zip(labels, values):
        result[class_name_from_code(int(label))] = float(value)
    total = sum(result.values())
    if not 0.999 <= total <= 1.001:
        raise ValueError(f"La salida de clases no suma uno: {total}")
    return result


def validate_class_mapping(mapping: Mapping[str, float]) -> None:
    if tuple(mapping) != CLASS_NAMES:
        raise ValueError(f"Orden de clases inesperado: {tuple(mapping)}; esperado: {CLASS_NAMES}")
