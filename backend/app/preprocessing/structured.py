"""Lecturas estructuradas del HUD con fallback temporal por variable."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np


def _rgb_array(frame: Any) -> np.ndarray:
    array = np.asarray(frame)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError("La región debe ser una imagen RGB")
    return array[:, :, :3].astype(np.float32)


@dataclass
class _BarReading:
    value: float | None
    confidence: float
    method: str
    reason: str | None = None


@dataclass
class _TrackState:
    value: float | None = None
    raw_value: float | None = None
    confidence: float = 0.0
    source: str = "bar_color_geometry"
    timestamp: float | None = None
    valid_count: int = 0
    history: deque[tuple[float, float]] | None = None


class HealthShieldReader:
    """Detector de barras con calidad y antigüedad independientes."""

    BAR_LEFT = 0.08
    BAR_RIGHT = 0.64
    Y_RANGES = {"shield": (0.50, 0.68), "health": (0.68, 0.90)}
    CURRENT_MAX_AGE = 1.0
    ESTIMATED_MAX_AGE = 3.0
    LAST_STABLE_MAX_AGE = 8.0

    def __init__(self, ttl_seconds: float = LAST_STABLE_MAX_AGE, history_size: int = 7, diagnostics: bool = False) -> None:
        self.ttl_seconds = ttl_seconds
        self.history_size = history_size
        self.tracks = {name: _TrackState(history=deque(maxlen=history_size)) for name in ("health", "shield")}
        self.diagnostics_enabled = diagnostics
        self._diagnostics: dict[str, dict[str, Any]] = {}

    def read_debug(self, crop: Any, timestamp: float | None = None) -> dict[str, Any]:
        previous = self.diagnostics_enabled
        self.diagnostics_enabled = True
        try:
            return {"reading": self.read(crop, timestamp), "regions": dict(self._diagnostics)}
        finally:
            self.diagnostics_enabled = previous

    def read(self, crop: Any, timestamp: float | None = None) -> dict[str, Any]:
        now = timestamp if timestamp is not None else time.time()
        try:
            image = _rgb_array(crop)
        except ValueError as exc:
            return self._payload(now, {name: self._fallback(name, now, str(exc)) for name in self.tracks}, "not_detected", str(exc))
        raw = {name: self._detect_bar(image, name) for name in self.tracks}
        readings = {name: self._resolve(name, value, now) for name, value in raw.items()}
        visible = [item for item in readings.values() if item["value"] is not None]
        current = [item for item in visible if item["status"] == "current"]
        overall = "available" if current or visible else "not_detected"
        return self._payload(now, readings, overall, None if visible else "No se obtuvo una lectura reciente del HUD")

    def _resolve(self, name: str, raw: _BarReading, now: float) -> dict[str, Any]:
        track = self.tracks[name]
        if raw.value is not None and raw.confidence >= 0.55:
            values = track.history or deque(maxlen=self.history_size)
            median = float(np.median([item[0] for item in values])) if values else raw.value
            if len(values) >= 3 and abs(raw.value - median) > max(25.0, median * 0.35):
                return self._fallback(name, now, "Lectura aislada rechazada por consistencia temporal", raw)
            values.append((raw.value, raw.confidence))
            track.history = values
            track.raw_value = raw.value
            track.value = raw.value if len(values) < 3 else float(np.median([item[0] for item in values]))
            track.confidence = float(min(raw.confidence, np.median([item[1] for item in values])))
            track.source = raw.method
            track.timestamp = now
            track.valid_count += 1
            quality = "high" if track.confidence >= 0.80 else "medium"
            return self._reading(track, now, "current", quality, raw.reason)
        return self._fallback(name, now, raw.reason or "Lectura de barra con confianza insuficiente", raw)

    def _fallback(self, name: str, now: float, reason: str, raw: _BarReading | None = None) -> dict[str, Any]:
        track = self.tracks[name]
        if track.value is None or track.timestamp is None:
            return {"value": None, "rawValue": raw.value if raw else None, "confidence": raw.confidence if raw else 0.0, "quality": "low", "source": raw.method if raw else track.source, "ageMs": None, "status": "no_reading", "reason": reason, "validCount": track.valid_count}
        age = max(0.0, now - track.timestamp)
        if age <= self.CURRENT_MAX_AGE:
            status, quality = "estimated", "medium"
        elif age <= self.ESTIMATED_MAX_AGE:
            status, quality = "estimated", "medium"
        elif age <= self.ttl_seconds:
            status, quality = "last_stable", "low"
        else:
            return {"value": None, "rawValue": raw.value if raw else track.raw_value, "confidence": 0.0, "quality": "low", "source": track.source, "ageMs": round(age * 1000), "status": "stale", "reason": "La última lectura superó su tiempo máximo de validez", "validCount": track.valid_count}
        return self._reading(track, now, status, quality, reason, raw)

    @staticmethod
    def _reading(track: _TrackState, now: float, status: str, quality: str, reason: str | None, raw: _BarReading | None = None) -> dict[str, Any]:
        age = None if track.timestamp is None else round(max(0.0, now - track.timestamp) * 1000)
        return {"value": round(float(np.clip(track.value, 0, 100)), 2) if track.value is not None else None, "rawValue": raw.value if raw else track.raw_value, "confidence": round(track.confidence if raw is None else min(track.confidence, raw.confidence), 3), "quality": quality, "source": track.source, "ageMs": age, "status": status, "reason": reason, "validCount": track.valid_count}

    def _detect_bar(self, image: np.ndarray, name: str) -> _BarReading:
        height, width = image.shape[:2]
        if height < 12 or width < 24:
            return _BarReading(None, 0.0, "bar_color_geometry", "ROI demasiado pequeña")
        red, green, blue = image[:, :, 0], image[:, :, 1], image[:, :, 2]
        saturation = image.max(axis=2) - image.min(axis=2)
        if name == "health":
            mask = (green >= 65) & (green > red * 1.12 + 8) & (green > blue * 1.08 + 8) & (saturation >= 28)
        else:
            mask = (blue >= 65) & (blue > red * 1.12 + 8) & (blue > green * 1.03 + 5) & (saturation >= 28)
        y0, y1 = int(height * self.Y_RANGES[name][0]), int(height * self.Y_RANGES[name][1])
        x0, x1 = int(width * self.BAR_LEFT), min(width, int(width * self.BAR_RIGHT))
        band_mask = mask[y0:max(y0 + 1, y1), x0:x1]
        row_scores = band_mask.sum(axis=1)
        if not len(row_scores) or int(row_scores.max()) < max(4, int((x1 - x0) * 0.06)):
            return _BarReading(None, 0.0, "bar_color_geometry", "Relleno de barra no localizado")
        peak = int(np.argmax(row_scores)); peak_score = float(row_scores[peak]); rows = np.flatnonzero(row_scores >= max(4, peak_score * 0.55))
        if len(rows) == 0:
            return _BarReading(None, 0.0, "bar_color_geometry", "Banda horizontal incoherente")
        bar_band = band_mask[int(rows.min()):int(rows.max()) + 1]; column_scores = bar_band.sum(axis=0); active = column_scores >= max(1, int(bar_band.shape[0] * 0.28)); runs: list[tuple[int, int]] = []; start: int | None = None
        for index, value in enumerate(active):
            if value and start is None: start = index
            if start is not None and (not value or index == len(active) - 1):
                end = index if value and index == len(active) - 1 else index - 1
                if end - start + 1 >= max(3, int(width * 0.01)): runs.append((start, end))
                start = None
        if not runs:
            return _BarReading(None, 0.0, "bar_color_geometry", "No hay continuidad horizontal suficiente")
        run_start, run_end = max(runs, key=lambda pair: pair[1] - pair[0]); filled_left, filled_right = x0 + run_start, x0 + run_end; total_right = max(filled_right, int(width * 0.60)); value = float(np.clip((filled_right - filled_left + 1) / max(1, total_right - filled_left + 1) * 100.0, 0.0, 100.0))
        row_quality = float(np.clip(peak_score / max(1, int((x1 - x0) * 0.25)), 0.0, 1.0)); position = float(np.clip(1.0 - abs(((filled_left + filled_right) / 2 / width) - 0.35), 0.0, 1.0)); confidence = float(np.clip(0.45 * row_quality + 0.40 + 0.15 * position, 0.0, 1.0))
        if self.diagnostics_enabled: self._diagnostics[name] = {"yRange": [y0, y1], "xRange": [filled_left, total_right], "filledBounds": [filled_left, filled_right], "value": round(value, 2), "confidence": round(confidence, 3)}
        return _BarReading(round(value, 2), confidence, "bar_color_geometry")

    def _payload(self, now: float, readings: dict[str, dict[str, Any]], status: str, reason: str | None) -> dict[str, Any]:
        health, shield = readings["health"], readings["shield"]; values = [item["value"] for item in readings.values() if item["value"] is not None]
        return {"status": status, "healthValue": health["value"], "shieldValue": shield["value"], "confidence": round(float(min([item["confidence"] for item in readings.values() if item["value"] is not None] or [0.0])), 3), "healthConfidence": health["confidence"], "shieldConfidence": shield["confidence"], "healthReading": health, "shieldReading": shield, "timestamp": now, "regionUsed": "health_hud_relative", "reason": reason, "dataStale": status in {"stale", "not_detected"}, "hasValue": bool(values)}


class InventoryReader:
    def read(self, crop: Any, timestamp: float | None = None) -> dict[str, Any]:
        now = timestamp if timestamp is not None else time.time()
        try: image = _rgb_array(crop)
        except ValueError as exc: return {"status": "unavailable", "slots": [], "timestamp": now, "reason": str(exc), "regionUsed": "inventory_hud"}
        height, width = image.shape[:2]; slots: list[dict[str, Any]] = []; slot_width = max(1, width // 5); partial = width < 50 or height < 20
        for index in range(5):
            left = index * slot_width; right = width if index == 4 else min(width, (index + 1) * slot_width); slot = image[:, left:right]; brightness = slot.mean(axis=2); saturation = slot.max(axis=2) - slot.min(axis=2); occupied_ratio = float(((brightness > 25) & (saturation > 12)).mean()) if slot.size else 0.0; occupied = occupied_ratio >= 0.04; rarity, rarity_conf = self._rarity(slot, occupied); confidence = float(np.clip(max(occupied_ratio * 2.0, rarity_conf), 0.0, 1.0)) if occupied else 1.0
            slots.append({"position": index + 1, "occupied": occupied, "category": None, "name": None, "rarity": rarity, "ammo": None, "quantity": None, "confidence": confidence, "occupiedRatio": occupied_ratio})
        status = "low_confidence" if partial or any(slot["occupied"] and slot["confidence"] < 0.25 for slot in slots) else "ready"
        return {"status": status, "slots": slots, "timestamp": now, "regionUsed": "inventory_hud", "reason": "Región parcialmente visible" if partial else None, "dataStale": False}

    @staticmethod
    def _rarity(slot: np.ndarray, occupied: bool) -> tuple[str | None, float]:
        if not occupied or slot.size == 0: return None, 1.0
        mean = slot.reshape(-1, 3).mean(axis=0); index = int(np.argmax(mean)); strength = float((mean[index] - np.mean(np.delete(mean, index))) / 255.0)
        if strength < 0.08: return None, 0.2
        return ("azul", "verde", "rojo")[index], float(np.clip(strength * 4.0, 0.0, 1.0))
