"""Diagnóstico independiente de WASAPI, modelo y evento de audio.

No escribe audio: solo mantiene la ventana en memoria y muestra métricas.
"""
from __future__ import annotations

import argparse
import asyncio
import time
import threading
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audio.capture import AudioConfig, LoopbackAudioCapture, loopback_capability  # noqa: E402
from app.audio.model import waveform_quality  # noqa: E402
from app.inference.service import InferenceService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--tone", action="store_true", help="Reproduce un tono temporal para validar la señal")
    args = parser.parse_args()
    print({"capability": loopback_capability()})
    capture = LoopbackAudioCapture(AudioConfig())
    try:
        print({"stage": "open", "device": capture.open()})
        service = InferenceService()
        print({"stage": "model", "status": service.status(), "version": service.versions.get("audio_raw")})
        if args.tone:
            import winsound
            threading.Thread(target=lambda: winsound.Beep(880, int(args.seconds * 1000)), daemon=True).start()
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            started = time.perf_counter()
            waveform = capture.read()
            quality = waveform_quality(waveform)
            prediction = service.predict_audio_waveform(waveform, quality)
            print({"stage": "capture", "samples": int(waveform.size), "quality": quality, "prediction_status": prediction.get("status"), "class": prediction.get("predictedClass"), "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
    except Exception as exc:  # noqa: BLE001 - el diagnóstico debe imprimir la causa exacta
        print({"stage": "error", "type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
