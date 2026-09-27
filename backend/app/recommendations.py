from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class RecommendationRule:
    code: str
    title: str
    priority: str
    source: str
    validity_seconds: int


@dataclass
class HealthAlertGate:
    """Persistencia e histéresis para no alertar por una lectura aislada."""
    low_health_count: int = 0
    low_shield_count: int = 0
    health_active: bool = False
    shield_active: bool = False
    health_medium_count: int = 0
    shield_medium_count: int = 0
    health_low_since: float | None = None
    shield_low_since: float | None = None

    def update(self, health: float | None, shield: float | None, confidence: float, status: str, health_confidence: float | None = None, shield_confidence: float | None = None, health_state: dict[str, Any] | None = None, shield_state: dict[str, Any] | None = None, now: float | None = None) -> set[str]:
        import time
        current_time = time.monotonic() if now is None else now
        health_state = health_state or {"value": health, "confidence": health_confidence if health_confidence is not None else confidence, "status": "current" if status == "available" else status}
        shield_state = shield_state or {"value": shield, "confidence": shield_confidence if shield_confidence is not None else confidence, "status": "current" if status == "available" else status}
        health_conf = float(health_state.get("confidence", 0.0))
        shield_conf = float(shield_state.get("confidence", 0.0))
        health_recent = health_state.get("status") in {"current", "estimated"} and health_conf >= 0.55
        shield_recent = shield_state.get("status") in {"current", "estimated"} and shield_conf >= 0.55
        health_high = health_recent and health_conf >= 0.80
        shield_high = shield_recent and shield_conf >= 0.80
        health = health_state.get("value")
        shield = shield_state.get("value")
        if health_recent and health is not None and health < 40:
            self.low_health_count += 1
        elif health is not None and health > 45:
            self.low_health_count = 0
            self.health_active = False
        else:
            self.low_health_count = 0
        if shield_recent and shield is not None and shield < 30:
            self.low_shield_count += 1
        elif shield is not None and shield > 35:
            self.low_shield_count = 0
            self.shield_active = False
        else:
            self.low_shield_count = 0
        self.health_medium_count = self.health_medium_count + 1 if health_recent and not health_high and health is not None and health < 40 else 0
        self.shield_medium_count = self.shield_medium_count + 1 if shield_recent and not shield_high and shield is not None and shield < 30 else 0
        if health_recent and health is not None and health < 40:
            self.health_low_since = self.health_low_since if self.health_low_since is not None else current_time
        else:
            self.health_low_since = None
        if shield_recent and shield is not None and shield < 30:
            self.shield_low_since = self.shield_low_since if self.shield_low_since is not None else current_time
        else:
            self.shield_low_since = None
        enabled: set[str] = set()
        health_confirmed = health_high and self.low_health_count >= 3 or self.health_medium_count >= 5 or self.health_low_since is not None and current_time - self.health_low_since >= 3
        shield_confirmed = shield_high and self.low_shield_count >= 3 or self.shield_medium_count >= 5 or self.shield_low_since is not None and current_time - self.shield_low_since >= 3
        if health_confirmed and not self.health_active:
            self.health_active = True
            enabled.add("LOW_HEALTH")
        if shield_confirmed and not self.shield_active:
            self.shield_active = True
            enabled.add("LOW_SHIELD")
        return enabled


RULES = (
    RecommendationRule("LOW_HEALTH", "Vida baja", "alta", "health_shield", 15),
    RecommendationRule("LOW_SHIELD", "Escudo bajo", "media", "health_shield", 15),
    RecommendationRule("NO_HEALING", "Sin curación detectada", "media", "inventory", 30),
    RecommendationRule("HIGH_ELIMINATION_RISK", "Riesgo elevado de ser eliminado", "alta", "multimodal", 15),
)


def _recommendation(rule: RecommendationRule, session_id: str, trigger_data: dict[str, Any], description: str) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc)
    return {
        "id": f"rec-{rule.code.lower()}-{int(timestamp.timestamp() * 1000)}",
        "code": rule.code,
        "title": rule.title,
        "text": rule.title,
        "explanation": description,
        "priority": rule.priority,
        "source": rule.source,
        "triggerData": trigger_data,
        "timestamp": timestamp.isoformat(),
        "validity": f"{rule.validity_seconds} s",
        "validUntil": (timestamp + timedelta(seconds=rule.validity_seconds)).isoformat(),
        "sessionId": session_id,
    }


def evaluate(session_id: str, health: float | None = None, shield: float | None = None, has_healing: bool | None = None, enabled_alerts: set[str] | None = None) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if health is not None and health < 40 and (enabled_alerts is None or "LOW_HEALTH" in enabled_alerts):
        recommendations.append(_recommendation(RULES[0], session_id, {"health": health}, "La lectura actual de vida está por debajo de 50/100."))
    if shield is not None and shield < 30 and (enabled_alerts is None or "LOW_SHIELD" in enabled_alerts):
        recommendations.append(_recommendation(RULES[1], session_id, {"shield": shield}, "La lectura actual de escudo está por debajo de 30/100."))
    if has_healing is False:
        recommendations.append(_recommendation(RULES[2], session_id, {"hasHealing": False}, "El inventario disponible no contiene un consumible de curación identificado."))
    return recommendations


def evaluate_prediction(session_id: str, eliminated_probability: float, missing_modalities: list[str]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    if eliminated_probability >= 0.70:
        rule = RULES[3]
        recommendations.append(_recommendation(rule, session_id, {"eliminatedProbability": eliminated_probability}, "La probabilidad multimodal de la clase Eliminado supera 70/100."))
    if missing_modalities:
        rule = RecommendationRule("MISSING_MODALITY", "Modalidad no disponible", "baja", "system", 10)
        recommendations.append(_recommendation(rule, session_id, {"missingModalities": missing_modalities}, "La predicción continúa con degradación controlada y sin inventar datos."))
    return recommendations
