from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RawAudioConfig:
    sample_rate: int = 32_000
    window_sec: float = 3.0
    n_fft: int = 1024
    hop_length: int = 512
    n_mels: int = 64


def _logmel(waveforms: np.ndarray, config: RawAudioConfig) -> np.ndarray:
    values = np.asarray(waveforms, dtype=np.float32)
    if values.ndim == 1:
        values = values[None, :]
    target = int(config.sample_rate * config.window_sec)
    result = []
    window = np.hanning(config.n_fft).astype(np.float32)
    for signal in values:
        signal = signal[:target]
        if signal.size < target:
            signal = np.pad(signal, (0, target - signal.size))
        frames = []
        for start in range(0, max(1, target - config.n_fft + 1), config.hop_length):
            chunk = signal[start:start + config.n_fft]
            if chunk.size < config.n_fft:
                chunk = np.pad(chunk, (0, config.n_fft - chunk.size))
            frames.append(np.abs(np.fft.rfft(chunk * window)) ** 2)
        power = np.asarray(frames, dtype=np.float32)
        # Representación calculada internamente desde la onda; el contrato del
        # modelo sigue recibiendo waveform, no un PNG precomputado.
        pooled = np.array_split(power[:, 1:], config.n_mels, axis=1)
        mel = np.stack([part.mean(axis=1) if part.size else np.zeros(power.shape[0]) for part in pooled], axis=1)
        result.append(np.log(np.maximum(mel, 1e-10)).reshape(-1))
    return np.asarray(result, dtype=np.float32)


class RawAudioClassifier:
    """Adaptador serializable para un clasificador ligero sobre waveform crudo."""

    def __init__(self, model, config: RawAudioConfig | None = None):
        self.model = model
        self.config = config or RawAudioConfig()

    def fit(self, waveforms: np.ndarray, labels: np.ndarray):
        self.model.fit(_logmel(waveforms, self.config), labels)
        return self

    def predict_proba(self, waveforms: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(_logmel(waveforms, self.config))

    @property
    def classes_(self):
        return self.model.classes_

    @property
    def n_features_in_(self):
        return int(self.config.sample_rate * self.config.window_sec)


def waveform_quality(waveform: np.ndarray) -> dict[str, float | bool]:
    values = np.asarray(waveform, dtype=np.float32).reshape(-1)
    rms = float(np.sqrt(np.mean(values * values) + 1e-12)) if values.size else 0.0
    silence = float(np.mean(np.abs(values) < 0.005)) if values.size else 1.0
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    dbfs = float(20.0 * np.log10(max(rms, 1e-7)))
    level = float(np.clip((dbfs + 60.0) / 60.0 * 100.0, 0.0, 100.0))
    return {"rms": rms, "silencePct": silence, "peak": peak, "dbfs": dbfs, "level": level, "clipped": peak >= 0.999, "silence": silence >= 0.98 or rms < 1e-4}
