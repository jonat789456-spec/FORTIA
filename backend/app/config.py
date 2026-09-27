from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int_env("PORT", 8000)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    videos_root: Path = Path(os.getenv("DATA_VIDEOS_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS"))
    dataframe_root: Path = Path(os.getenv("DATA_DF_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF"))
    model_registry: Path = Path(os.getenv("MODEL_REGISTRY", "artifacts/registry.json"))
    capture_fps: int = _int_env("CAPTURE_FPS", 15)
    stream_fps: int = _int_env("STREAM_FPS", 10)
    inference_interval_sec: float = _float_env("INFERENCE_INTERVAL_SEC", 1.0)
    capture_window_title: str = os.getenv("CAPTURE_WINDOW_TITLE", "Fortnite")
    capture_window_title_exact: bool = os.getenv("CAPTURE_WINDOW_TITLE_EXACT", "false").casefold() == "true"
    # En modo ventana sin bordes, Fortnite puede exponer una ventana visible
    # sin título. El proceso principal es un identificador más fiable que el
    # texto de la barra de título.
    capture_process_name: str = os.getenv("CAPTURE_PROCESS_NAME", "FortniteClient-Win64-Shipping")
    capture_mode: str = os.getenv("CAPTURE_MODE", "fortnite")


settings = Settings()
