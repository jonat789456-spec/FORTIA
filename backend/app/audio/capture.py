from __future__ import annotations

from dataclasses import dataclass
import ctypes
import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 32_000
    capture_sample_rate: int = 48_000
    n_mels: int = 128
    n_fft: int = 2_048
    hop_length: int = 512
    duration_sec: float = 3.0
    hop_sec: float = 1.0
    block_size: int = 0


class LoopbackAudioCapture:
    """Captura la salida del sistema mediante WASAPI loopback, nunca el micrófono."""

    def __init__(self, config: AudioConfig = AudioConfig(), preferred_device: str | None = None) -> None:
        self.config = config
        self.preferred_device = preferred_device
        self.microphone = None
        self.device_name: str | None = None
        self.device_id: str | None = None
        self.channels: int | None = None
        self.native_sample_rate: int | None = None
        self.last_error: str | None = None
        self.blocks_received = 0
        self._buffer = np.empty(0, dtype=np.float32)
        self._lock = threading.Lock()

    def open(self) -> str:
        try:
            self._initialize_com_for_current_thread()
            import soundcard as sc  # type: ignore

            speakers = list(sc.all_speakers())
            if not speakers:
                raise RuntimeError("Windows no reportó dispositivos de reproducción")
            # La configuración explícita tiene prioridad, pero un nombre que
            # ya no existe no debe dejar todo el backend sin captura: se cae
            # al predeterminado y finalmente al primer endpoint compatible.
            speaker = None
            if self.preferred_device:
                wanted = self.preferred_device.casefold().strip()
                if wanted.isdigit() and int(wanted) < len(speakers):
                    speaker = speakers[int(wanted)]
                else:
                    speaker = next((item for item in speakers if str(item.name).casefold() == wanted or str(getattr(item, "id", "")).casefold() == wanted), None)
                if speaker is None:
                    logger.warning("AUDIO_OUTPUT_DEVICE=%s no fue encontrado; se usará el dispositivo predeterminado", self.preferred_device)
            if speaker is None:
                speaker = sc.default_speaker()
            if speaker is None:
                speaker = speakers[0]
            if speaker is None:
                raise RuntimeError(f"No existe el dispositivo de salida configurado: {self.preferred_device or 'predeterminado'}")
            self.microphone = sc.get_microphone(id=str(getattr(speaker, "id", speaker.name)), include_loopback=True)
            self.device_name = str(speaker.name)
            self.device_id = str(getattr(speaker, "id", speaker.name))
            self.channels = int(getattr(speaker, "channels", 0) or 0) or None
            self.last_error = None
            logger.info("WASAPI Loopback seleccionado: name=%s id=%s sample_rate=%s channels=%s block=%s", self.device_name, self.device_id, self.native_sample_rate or self.config.capture_sample_rate, self.channels, self.config.block_size or int(self.config.capture_sample_rate * self.config.duration_sec))
            return self.device_name
        except (ImportError, OSError, RuntimeError) as exc:
            raise RuntimeError(f"WASAPI loopback no disponible: {exc}") from exc

    @staticmethod
    def _initialize_com_for_current_thread() -> None:
        if hasattr(ctypes, "windll"):
            # soundcard usa Media Foundation/WASAPI y la captura ocurre en un
            # worker; COM debe inicializarse explícitamente en ese hilo.
            ctypes.windll.ole32.CoInitialize(None)

    def read(self) -> np.ndarray:
        # asyncio.to_thread puede reutilizar otro worker entre bloques. WASAPI
        # requiere COM inicializado en el hilo que ejecuta record(), no solo en
        # el hilo donde se abrió el endpoint.
        self._initialize_com_for_current_thread()
        if self.microphone is None:
            self.open()
        native_rates = [self.native_sample_rate] if self.native_sample_rate else [self.config.capture_sample_rate, 44_100, self.config.sample_rate]
        target = int(self.config.sample_rate * self.config.duration_sec)
        chunk_target = max(1, int(self.config.sample_rate * min(self.config.hop_sec, self.config.duration_sec)))
        last_error: Exception | None = None
        while self._buffer.size < target:
            values = None
            for native_rate in native_rates:
                try:
                    frames = max(1, int(np.ceil(chunk_target * native_rate / self.config.sample_rate)))
                    with self._lock:
                        values = self.microphone.record(numframes=frames, samplerate=native_rate)
                    self.native_sample_rate = native_rate
                    break
                except (OSError, RuntimeError, ValueError) as exc:
                    last_error = exc
            if values is None:
                self.last_error = str(last_error)
                raise RuntimeError(f"No se pudo leer el dispositivo WASAPI: {last_error}")
            array = np.asarray(values, dtype=np.float32)
            if array.ndim == 2:
                array = array.mean(axis=1)
            array = array.reshape(-1)
            native_target = array.size
            resampled_target = max(1, int(round(native_target * self.config.sample_rate / self.native_sample_rate)))
            if native_target != resampled_target:
                source_axis = np.linspace(0.0, 1.0, native_target, endpoint=False)
                target_axis = np.linspace(0.0, 1.0, resampled_target, endpoint=False)
                array = np.interp(target_axis, source_axis, array).astype(np.float32)
            self._buffer = np.concatenate((self._buffer, array))
            self.blocks_received += 1
            logger.debug("WASAPI bloque recibido: number=%s native_samples=%s model_samples=%s buffer_samples=%s", self.blocks_received, native_target, array.size, self._buffer.size)
        return self._buffer[-target:].copy()

    def close(self) -> None:
        self.microphone = None
        self.native_sample_rate = None
        self._buffer = np.empty(0, dtype=np.float32)


def loopback_capability() -> dict[str, object]:
    try:
        LoopbackAudioCapture._initialize_com_for_current_thread()
        import soundcard as sc  # type: ignore

        speaker = sc.default_speaker()
        devices = [{"index": index, "id": str(getattr(item, "id", item.name)), "name": str(item.name), "api": "WASAPI Loopback", "outputChannels": getattr(item, "channels", None), "default": bool(speaker and item.name == speaker.name), "loopback": True} for index, item in enumerate(sc.all_speakers())]
        return {"available": speaker is not None, "source": "wasapi_loopback", "device": str(speaker.name) if speaker else None, "deviceId": str(getattr(speaker, "id", speaker.name)) if speaker else None, "microphone": False, "devices": devices, "reason": None if speaker else "Dispositivo de salida no encontrado"}
    except (ImportError, OSError, RuntimeError) as exc:
        return {"available": False, "source": "wasapi_loopback", "device": None, "microphone": False, "reason": str(exc)}


def mel_spectrogram(audio: np.ndarray, config: AudioConfig = AudioConfig()) -> np.ndarray:
    """Transformación histórica para pruebas; la inferencia raw usa waveform."""
    signal = np.asarray(audio, dtype=np.float32).reshape(-1)
    target = int(config.sample_rate * config.duration_sec)
    if signal.size < target:
        signal = np.pad(signal, (0, target - signal.size))
    signal = signal[:target]
    frames = []
    window = np.hanning(config.n_fft).astype(np.float32)
    for start in range(0, max(1, len(signal) - config.n_fft + 1), config.hop_length):
        chunk = signal[start:start + config.n_fft]
        if len(chunk) < config.n_fft:
            chunk = np.pad(chunk, (0, config.n_fft - len(chunk)))
        frames.append(np.abs(np.fft.rfft(chunk * window)) ** 2)
    power = np.stack(frames, axis=1)
    bands = np.array_split(power, config.n_mels, axis=0)
    mel = np.stack([band.mean(axis=0) if band.size else np.zeros(power.shape[1]) for band in bands], axis=0)
    return np.log(np.maximum(mel, 1e-10)).astype(np.float32)
