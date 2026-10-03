"""Señales temporales de riesgo y estado estable para FORTIA.

Este módulo no modifica las probabilidades de la cabeza principal. La señal de
seguridad se publica por separado y el modelo experimental puede consumir las
características que aquí se calculan cuando exista un artefacto entrenado.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RiskPoint:
    timestamp: float
    health: float | None
    shield: float | None
    audio_activity: float | None = None
    storm: float | None = None
    enemy_persistence: float | None = None
    healing_available: float | None = None
    ammo_available: float | None = None
    cover_available: float | None = None


def _value(payload: dict[str, Any] | None, *keys: str) -> float | None:
    if not payload:
        return None
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    try:
        value = float(current)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def point_from_payload(payload: dict[str, Any], timestamp: float | None = None) -> RiskPoint:
    """Construye un punto sin convertir lecturas desconocidas a 0 o 100."""
    health = _value(payload, "healthValue")
    shield = _value(payload, "shieldValue")
    return RiskPoint(
        timestamp=float(timestamp if timestamp is not None else payload.get("timestamp", 0.0)),
        health=health,
        shield=shield,
        audio_activity=_value(payload, "audioActivity"),
        storm=_value(payload, "storm"),
        enemy_persistence=_value(payload, "enemyPersistence"),
        healing_available=_value(payload, "healingAvailable"),
        ammo_available=_value(payload, "ammoAvailable"),
        cover_available=_value(payload, "coverAvailable"),
    )


class TemporalRiskFeatures:
    """Calcula tendencias causales usando únicamente observaciones anteriores."""

    HORIZONS = (1.0, 3.0, 5.0)

    def __init__(self, max_points: int = 64) -> None:
        self.points: deque[RiskPoint] = deque(maxlen=max_points)

    def reset(self) -> None:
        self.points.clear()

    def add(self, point: RiskPoint) -> dict[str, float | None]:
        self.points.append(point)
        return self.features()

    def _prior(self, timestamp: float, horizon: float) -> RiskPoint | None:
        candidates = [point for point in self.points if point.timestamp <= timestamp - horizon + 1e-6]
        return candidates[-1] if candidates else None

    @staticmethod
    def _delta(current: float | None, previous: float | None) -> float | None:
        return None if current is None or previous is None else current - previous

    def features(self) -> dict[str, float | None]:
        if not self.points:
            return {}
        current = self.points[-1]
        result: dict[str, float | None] = {
            "health.current": current.health,
            "shield.current": current.shield,
            "health_shield.current": None if current.health is None or current.shield is None else current.health + current.shield,
            "audio.activity": current.audio_activity,
            "storm": current.storm,
            "enemy.persistence": current.enemy_persistence,
            "healing.available": current.healing_available,
            "ammo.available": current.ammo_available,
            "cover.available": current.cover_available,
        }
        for horizon in self.HORIZONS:
            prior = self._prior(current.timestamp, horizon)
            suffix = f".{int(horizon)}s"
            result[f"health.delta{suffix}"] = self._delta(current.health, prior.health if prior else None)
            result[f"shield.delta{suffix}"] = self._delta(current.shield, prior.shield if prior else None)
            result[f"health_shield.delta{suffix}"] = self._delta(
                None if current.health is None or current.shield is None else current.health + current.shield,
                None if not prior or prior.health is None or prior.shield is None else prior.health + prior.shield,
            )
        result["time_since_damage"] = self._time_since_damage(current.timestamp)
        result["time_critical"] = self._time_critical(current.timestamp)
        result["recent_damage_count"] = float(self._recent_damage_count(current.timestamp))
        result["consecutive_drops"] = float(self._consecutive_drops())
        return result

    def _time_since_damage(self, now: float) -> float | None:
        for left, right in zip(reversed(self.points), list(reversed(self.points)) [1:]):
            if left.health is not None and right.health is not None and left.health < right.health:
                return max(0.0, now - left.timestamp)
        return None

    def _time_critical(self, now: float) -> float | None:
        start: float | None = None
        for point in reversed(self.points):
            critical = point.health is not None and point.health <= 25
            if not critical:
                break
            start = point.timestamp
        return None if start is None else max(0.0, now - start)

    def _recent_damage_count(self, now: float) -> int:
        points = [point for point in self.points if now - point.timestamp <= 5.0]
        return sum(1 for left, right in zip(points, points[1:]) if left.health is not None and right.health is not None and left.health < right.health)

    def _consecutive_drops(self) -> int:
        count = 0
        for left, right in zip(reversed(self.points), list(reversed(self.points))[1:]):
            if left.health is not None and right.health is not None and left.health < right.health:
                count += 1
            else:
                break
        return count


@dataclass
class RiskSmoother:
    """Suavizado causal con activación rápida y desactivación por recuperación."""

    alpha: float = 0.45
    value: float | None = None
    active: bool = False
    weak_count: int = 0

    def reset(self) -> None:
        self.value = None
        self.active = False
        self.weak_count = 0

    def update(self, probability: float | None, abrupt_drop: bool = False) -> float | None:
        if probability is None:
            return self.value
        probability = float(np.clip(probability, 0.0, 1.0))
        if self.value is None:
            self.value = probability
        else:
            alpha = min(0.95, self.alpha + 0.35) if abrupt_drop else self.alpha
            self.value = alpha * probability + (1.0 - alpha) * self.value
        if self.value >= 0.65 or abrupt_drop:
            self.active = True
            self.weak_count = 0
        elif self.value < 0.40:
            self.weak_count += 1
            if self.weak_count >= 2:
                self.active = False
        return self.value


def safety_signal(features: dict[str, float | None]) -> dict[str, Any]:
    """Capa explicable separada; no es una probabilidad del modelo."""
    health = features.get("health.current")
    health_delta = features.get("health.delta.1s")
    storm = features.get("storm")
    reasons: list[str] = []
    if health is not None and health <= 20:
        reasons.append("vida críticamente baja")
    if health_delta is not None and health_delta <= -15:
        reasons.append("caída rápida de vida")
    if storm is not None and storm >= 0.5 and health_delta is not None and health_delta < 0:
        reasons.append("tormenta con vida descendiendo")
    return {"active": bool(reasons), "reasons": reasons, "source": "regla_seguridad", "not_model_probability": True}
