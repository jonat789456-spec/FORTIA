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


def _bool_env(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int_env("PORT", 8000)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    frontend_origins: str = os.getenv("FRONTEND_ORIGINS", "")
    videos_root: Path = Path(os.getenv("DATA_VIDEOS_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS"))
    dataframe_root: Path = Path(os.getenv("DATA_DF_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF"))
    model_registry: Path = Path(os.getenv("MODEL_REGISTRY", "artifacts/registry.json"))
    capture_fps: int = _int_env("CAPTURE_FPS", 30)
    stream_fps: int = _int_env("STREAM_FPS", 30)
    stream_max_width: int = _int_env("STREAM_MAX_WIDTH", 1280)
    stream_fallback_width: int = _int_env("STREAM_FALLBACK_WIDTH", 960)
    stream_jpeg_quality: int = _int_env("STREAM_JPEG_QUALITY", 80)
    stream_max_bytes: int = _int_env("STREAM_MAX_BYTES", 850000)
    stream_adaptive: bool = _bool_env("STREAM_ADAPTIVE", True)
    stream_min_fps: int = _int_env("STREAM_MIN_FPS", 25)
    health_fast_fps: int = _int_env("HEALTH_FAST_FPS", 10)
    health_visible_fps: int = _int_env("HEALTH_VISIBLE_FPS", 10)
    health_verification_interval_sec: float = _float_env("HEALTH_VERIFICATION_INTERVAL_SEC", 1.0)
    health_current_max_age_sec: float = _float_env("HEALTH_CURRENT_MAX_AGE_SEC", 0.45)
    inference_interval_sec: float = _float_env("INFERENCE_INTERVAL_SEC", 1.0)
    audio_raw_root: Path = Path(os.getenv("AUDIO_RAW_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS\AUDIO_RAW"))
    audio_window_sec: float = _float_env("AUDIO_WINDOW_SEC", 3.0)
    audio_hop_sec: float = _float_env("AUDIO_HOP_SEC", 1.0)
    audio_save_debug: bool = os.getenv("AUDIO_SAVE_DEBUG", "false").casefold() == "true"
    audio_output_device: str = os.getenv("AUDIO_OUTPUT_DEVICE", "")
    capture_window_title: str = os.getenv("CAPTURE_WINDOW_TITLE", "Fortnite")
    capture_window_title_exact: bool = os.getenv("CAPTURE_WINDOW_TITLE_EXACT", "false").casefold() == "true"
    # En modo ventana sin bordes, Fortnite puede exponer una ventana visible
    # sin título. El proceso principal es un identificador más fiable que el
    # texto de la barra de título.
    capture_process_name: str = os.getenv("CAPTURE_PROCESS_NAME", "FortniteClient-Win64-Shipping")
    capture_mode: str = os.getenv("CAPTURE_MODE", "fortnite")
    web_frame_max_width: int = _int_env("WEB_FRAME_MAX_WIDTH", 1280)
    web_frame_max_bytes: int = _int_env("WEB_FRAME_MAX_BYTES", 250000)
    risk_experiment_artifact: Path = Path(os.getenv("RISK_EXPERIMENT_ARTIFACT", "artifacts/risk_experiment_v1/risk_multimodal.joblib"))
    risk_shadow_enabled: bool = _bool_env("RISK_SHADOW_ENABLED", False)
    failure_collection_enabled: bool = _bool_env("FAILURE_COLLECTION_ENABLED", False)
    failure_collection_root: Path = Path(os.getenv("FAILURE_COLLECTION_ROOT", "artifacts/real_game_failures"))
    failure_collection_max_cases: int = _int_env("FAILURE_COLLECTION_MAX_CASES", 500)


settings = Settings()
