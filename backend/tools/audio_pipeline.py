"""Auditoría, extracción y segmentación de audio crudo de FORTIA.

Los videos se abren únicamente para lectura. La extracción requiere ``ffprobe``
y ``ffmpeg`` en PATH o las variables ``FFPROBE_BIN``/``FFMPEG_BIN``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
VIDEOS_ROOT = Path(os.getenv("DATA_VIDEOS_ROOT", r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS"))
ORIGINAL_ROOT = VIDEOS_ROOT / "ORIGINAL"
AUDIO_ROOT = Path(os.getenv("AUDIO_RAW_ROOT", str(VIDEOS_ROOT / "AUDIO_RAW")))
MANIFEST_ROOT = ROOT / "backend" / "data" / "manifests"
REPORT_ROOT = ROOT / "backend" / "reports" / "audio_raw"
SPLIT_PATH = ROOT / "backend" / "data" / "splits" / "video_split.csv"
SAMPLE_RATE = 32_000


def _binary(name: str) -> str | None:
    value = os.getenv(name)
    return value or shutil.which(name.replace("_BIN", "").lower())


def _probe(path: Path) -> dict[str, object]:
    binary = _binary("FFPROBE_BIN")
    if not binary:
        raise RuntimeError("ffprobe no está disponible; instálalo o define FFPROBE_BIN")
    result = subprocess.run([binary, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=20)
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    return {
        "duration_sec": float((payload.get("format") or {}).get("duration") or 0.0),
        "video_codec": video.get("codec_name"),
        "audio_stream": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_channels": audio.get("channels") if audio else None,
        "audio_sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        "audio_bitrate": int(audio["bit_rate"]) if audio and audio.get("bit_rate") else None,
        "audio_duration_sec": float(audio.get("duration") or 0.0) if audio else None,
    }


def _split_index() -> dict[str, dict[str, object]]:
    frame = pd.read_csv(SPLIT_PATH, encoding="utf-8-sig")
    return {str(row.video): {"id_video": int(row.id_video), "class": str(row.clase), "label": int(row.etiqueta), "split": str(row.split)} for row in frame.itertuples()}


def _video_id(name: str, index: dict[str, dict[str, object]]) -> dict[str, object]:
    if name not in index:
        raise KeyError(f"Video no presente en el split oficial: {name}")
    return index[name]


def audit() -> pd.DataFrame:
    index = _split_index()
    ffprobe_available = os.getenv("AUDIO_AUDIT_PHYSICAL", "false").casefold() == "true" and bool(_binary("FFPROBE_BIN"))
    historical: dict[str, dict[str, object]] = {}
    historical_path = MANIFEST_ROOT / "file_manifest.csv"
    if historical_path.exists():
        old = pd.read_csv(historical_path, encoding="utf-8-sig", low_memory=False)
        for item in old[old.modality.eq("original") & old.extension.eq(".mp4")].itertuples():
            historical[str(item.path)] = {"duration_sec": item.duration_sec, "video_codec": item.video_codec, "audio_stream": bool(item.audio_codec), "audio_codec": item.audio_codec, "audio_channels": item.audio_channels, "audio_sample_rate": item.audio_sample_rate, "audio_bitrate": None, "audio_duration_sec": item.duration_sec}
    rows: list[dict[str, object]] = []
    candidates = [Path(value) for value in historical if Path(value).suffix.casefold() in {".mp4", ".mkv", ".mov", ".avi"}] if not ffprobe_available else sorted(ORIGINAL_ROOT.iterdir())
    for path in candidates:
        if (ffprobe_available and not path.is_file()) or path.suffix.casefold() not in {".mp4", ".mkv", ".mov", ".avi"}:
            continue
        meta = _video_id(path.name, index)
        row: dict[str, object] = {"id_video": meta["id_video"], "video_name": path.name, "video_path": str(path), "extension": path.suffix.lower(), "class": meta["class"], "label": meta["label"], "split": meta["split"], "audio_path": "", "status": "corrupted", "observations": ""}
        try:
            probe = _probe(path) if ffprobe_available else historical.get(str(path))
            if probe is None:
                raise RuntimeError("No existe ffprobe ni registro histórico para este video")
            row["probe_source"] = "ffprobe" if ffprobe_available else "file_manifest_historico"
            row.update({"video_duration_sec": probe["duration_sec"], "has_audio_stream": probe["audio_stream"], "codec": probe["audio_codec"], "channels": probe["audio_channels"], "sample_rate": probe["audio_sample_rate"], "bitrate": probe["audio_bitrate"], "audio_duration_sec": probe["audio_duration_sec"]})
            if not probe["audio_stream"]:
                row["status"] = "no_audio_stream"
            elif float(probe["audio_duration_sec"] or 0) < 0.5:
                row["status"] = "too_short"
            elif abs(float(probe["duration_sec"] or 0) - float(probe["audio_duration_sec"] or 0)) > 1.0:
                row["status"] = "duration_mismatch"
            else:
                row["status"] = "valid"
        except Exception as exc:  # noqa: BLE001 - queda registrado por video
            row["observations"] = str(exc)
        rows.append(row)
    frame = pd.DataFrame(rows).sort_values("id_video")
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(MANIFEST_ROOT / "audio_raw_manifest.csv", index=False, encoding="utf-8-sig")
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(), "total_videos": int(len(frame)), "with_audio": int((frame.status == "valid").sum()), "without_audio": int((frame.status == "no_audio_stream").sum()), "status_counts": frame.status.value_counts().to_dict(), "duration_total_sec": float(frame.get("audio_duration_sec", pd.Series(dtype=float)).fillna(0).sum()), "class_distribution": frame.groupby("class").size().to_dict() if not frame.empty else {}, "split_distribution": frame.groupby("split").size().to_dict() if not frame.empty else {}, "ffmpeg_available": bool(_binary("FFMPEG_BIN")), "ffprobe_available": bool(_binary("FFPROBE_BIN")), "probe_mode": "physical_ffprobe" if ffprobe_available else "historical_manifest"}
    (REPORT_ROOT / "audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ["# Auditoría de audio crudo", "", f"Generado: `{summary['generated_at']}`", "", f"- Videos auditados: **{summary['total_videos']}**", f"- Con audio válido: **{summary['with_audio']}**", f"- Sin pista de audio: **{summary['without_audio']}**", f"- Duración de audio: **{summary['duration_total_sec'] / 3600:.2f} h**", f"- FFmpeg: **{'disponible' if summary['ffmpeg_available'] else 'no disponible'}**", "", "## Estados", ""]
    report.extend(f"- `{key}`: {value}" for key, value in summary["status_counts"].items())
    (REPORT_ROOT / "AUDIO_AUDIT.md").write_text("\n".join(report), encoding="utf-8")
    return frame


def extract(manifest: Path | None = None) -> pd.DataFrame:
    frame = pd.read_csv(manifest or MANIFEST_ROOT / "audio_raw_manifest.csv", encoding="utf-8-sig")
    for column in ("audio_path", "audio_sha256", "observations"):
        if column not in frame:
            frame[column] = ""
        frame[column] = frame[column].fillna("").astype(object)
    binary = _binary("FFMPEG_BIN")
    if not binary:
        raise RuntimeError("ffmpeg no está disponible; no se extrae ningún archivo")
    AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
    for index, row in frame.iterrows():
        if row.status != "valid":
            continue
        target = AUDIO_ROOT / f"video_{int(row.id_video):04d}_audio.wav"
        if not target.exists():
            subprocess.run([binary, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(row.video_path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(target)], check=True)
        with wave.open(str(target), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getframerate() != SAMPLE_RATE or audio.getsampwidth() != 2:
                frame.at[index, "status"] = "extraction_error"
                frame.at[index, "observations"] = "Formato WAV inesperado"
                continue
            frame.at[index, "audio_duration_sec"] = audio.getnframes() / audio.getframerate()
        frame.at[index, "audio_path"] = str(target)
        frame.at[index, "audio_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    frame.to_csv(MANIFEST_ROOT / "audio_raw_manifest.csv", index=False, encoding="utf-8-sig")
    return frame


def segment(manifest: Path | None = None, window_sec: float = 3.0, hop_sec: float = 1.5) -> pd.DataFrame:
    frame = pd.read_csv(manifest or MANIFEST_ROOT / "audio_raw_manifest.csv", encoding="utf-8-sig")
    rows: list[dict[str, object]] = []
    for row in frame.rename(columns={"class": "class_name"}).itertuples():
        if row.status != "valid" or not row.audio_path or not Path(row.audio_path).exists():
            continue
        with wave.open(row.audio_path, "rb") as audio:
            samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        size, hop = int(window_sec * SAMPLE_RATE), int(hop_sec * SAMPLE_RATE)
        for start in range(0, max(1, len(samples) - size + 1), hop):
            chunk = samples[start:start + size]
            if len(chunk) < size:
                chunk = np.pad(chunk, (0, size - len(chunk)))
            rms = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
            rows.append({"segment_id": f"video_{int(row.id_video):04d}_{start:09d}", "id_video": row.id_video, "video_name": row.video_name, "audio_path": row.audio_path, "start_sec": start / SAMPLE_RATE, "end_sec": min((start + size) / SAMPLE_RATE, float(row.audio_duration_sec)), "duration_sec": min(window_sec, max(0.0, float(row.audio_duration_sec) - start / SAMPLE_RATE)), "class": row.class_name, "label": row.label, "split": row.split, "rms": rms, "silence_pct": float(np.mean(np.abs(chunk) < 0.005)), "status": "valid" if rms >= 1e-4 else "silence"})
    result = pd.DataFrame(rows)
    result.to_csv(MANIFEST_ROOT / "audio_segments.csv", index=False, encoding="utf-8-sig")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["audit", "extract", "segment", "all"])
    parser.add_argument("--window", type=float, default=3.0)
    parser.add_argument("--hop", type=float, default=1.5)
    args = parser.parse_args()
    if args.command in {"audit", "all"}:
        audit()
    if args.command in {"extract", "all"}:
        extract()
    if args.command in {"segment", "all"}:
        segment(window_sec=args.window, hop_sec=args.hop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
