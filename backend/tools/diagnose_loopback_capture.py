"""Prueba aislada de captura WASAPI Loopback.

Enumera entradas y salidas, abre únicamente el loopback de un altavoz,
guarda un WAV temporal y falla si todos los bloques son silencio. No ejecuta
el modelo ni depende del backend FastAPI.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.metadata
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np


def init_com() -> None:
    if hasattr(ctypes, "windll"):
        ctypes.windll.ole32.CoInitialize(None)


def device_info(item: object, index: int, default_id: str | None = None) -> dict[str, object]:
    device_id = str(getattr(item, "id", ""))
    return {
        "index": index,
        "id": device_id,
        "name": str(getattr(item, "name", item)),
        "channels": int(getattr(item, "channels", 0) or 0),
        "default": device_id == default_id,
        "hostApi": "WASAPI / Media Foundation (soundcard)",
    }


def write_wav(path: Path, samples: np.ndarray, sample_rate: int, channels: int) -> None:
    values = np.asarray(samples, dtype=np.float32)
    values = np.clip(values, -1.0, 1.0)
    pcm = (values * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--device", help="Nombre, ID o índice del altavoz; por defecto usa el predeterminado")
    parser.add_argument("--wav", type=Path, default=Path(".runtime/audio_loopback_diagnostic.wav"))
    parser.add_argument("--tone", action="store_true", help="Reproduce un tono de Windows durante la prueba")
    args = parser.parse_args()

    init_com()
    try:
        import soundcard as sc  # type: ignore
    except ImportError as exc:
        print(json.dumps({"ok": False, "error": f"soundcard no está instalado: {exc}"}, ensure_ascii=False))
        return 2

    version = importlib.metadata.version("soundcard")
    speakers = list(sc.all_speakers())
    microphones = list(sc.all_microphones())
    default = sc.default_speaker()
    default_id = str(getattr(default, "id", "")) if default else None
    print(json.dumps({
        "stage": "devices",
        "library": "soundcard",
        "version": version,
        "hostApi": "WASAPI / Media Foundation",
        "outputs": [device_info(item, index, default_id) for index, item in enumerate(speakers)],
        "inputs": [device_info(item, index) for index, item in enumerate(microphones)],
        "defaultOutput": device_info(default, -1, default_id) if default else None,
    }, ensure_ascii=False, indent=2))

    candidates = speakers
    if args.device:
        wanted = args.device.casefold().strip()
        if wanted.isdigit() and int(wanted) < len(speakers):
            candidates = [speakers[int(wanted)]]
        else:
            candidates = [item for item in speakers if wanted in str(getattr(item, "name", "")).casefold() or wanted == str(getattr(item, "id", "")).casefold()]
    elif default:
        candidates = [default] + [item for item in speakers if str(getattr(item, "id", "")) != default_id]

    errors: list[dict[str, str]] = []
    for speaker in candidates:
        name = str(speaker.name)
        device_id = str(getattr(speaker, "id", name))
        try:
            microphone = sc.get_microphone(id=device_id, include_loopback=True)
            sample_rate = 48_000
            channels = int(getattr(speaker, "channels", 0) or 2)
            block_seconds = 0.5
            blocks: list[np.ndarray] = []
            block_count = max(1, int(np.ceil(args.seconds / block_seconds)))
            if args.tone:
                import threading
                import winsound
                threading.Thread(target=lambda: winsound.Beep(880, int(args.seconds * 1000)), daemon=True).start()
            print(json.dumps({"stage": "capture_start", "device": name, "deviceId": device_id, "format": {"sampleRate": sample_rate, "channels": channels, "blockFrames": int(sample_rate * block_seconds), "mode": "shared", "loopback": True}}, ensure_ascii=False))
            started = time.perf_counter()
            for number in range(block_count):
                block = np.asarray(microphone.record(numframes=int(sample_rate * block_seconds), samplerate=sample_rate), dtype=np.float32)
                if block.ndim == 1:
                    block = block[:, None]
                channels = int(block.shape[1])
                blocks.append(block)
                mono = block.mean(axis=1)
                rms = float(np.sqrt(np.mean(mono * mono) + 1e-12))
                peak = float(np.max(np.abs(mono))) if mono.size else 0.0
                print(json.dumps({"stage": "block", "number": number + 1, "samples": int(block.shape[0]), "channels": channels, "rms": rms, "peak": peak}, ensure_ascii=False))
            values = np.concatenate(blocks, axis=0)[: int(args.seconds * sample_rate)]
            mono = values.mean(axis=1)
            rms = float(np.sqrt(np.mean(mono * mono) + 1e-12))
            peak = float(np.max(np.abs(mono))) if mono.size else 0.0
            write_wav(args.wav, values, sample_rate, channels)
            with wave.open(str(args.wav), "rb") as saved:
                saved_rms = float(np.sqrt(np.mean((np.frombuffer(saved.readframes(saved.getnframes()), dtype="<i2").astype(np.float32) / 32768.0) ** 2) + 1e-12))
            result = {"ok": rms > 1e-4 and peak > 1e-4 and saved_rms > 1e-4, "stage": "complete", "device": name, "deviceId": device_id, "sampleRate": sample_rate, "channels": channels, "samples": int(values.shape[0]), "blocks": len(blocks), "rms": rms, "peak": peak, "wav": str(args.wav), "wavRms": saved_rms, "elapsedSec": round(time.perf_counter() - started, 3)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 3
        except Exception as exc:  # noqa: BLE001 - conserva el error técnico por dispositivo
            errors.append({"device": name, "deviceId": device_id, "error": f"{type(exc).__name__}: {exc}"})
            print(json.dumps({"stage": "device_error", "device": name, "deviceId": device_id, "error": errors[-1]["error"]}, ensure_ascii=False))

    print(json.dumps({"ok": False, "stage": "failed", "errors": errors}, ensure_ascii=False, indent=2))
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
