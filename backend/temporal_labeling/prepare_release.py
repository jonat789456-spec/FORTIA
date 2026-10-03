"""Congela detector y crea inventario/muestra estratificada sin generar etiquetas."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd

from detector import REGIONS, TEXT_PATTERNS, VERSION, executable_versions, resolve_tesseract

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite")
VIDEOS = DATA / "VIDEOS" / "ORIGINAL"
OUT = ROOT / "backend" / "data" / "automatic_temporal_annotations" / "release_v0.3.0"
SEED = 20261001


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def probe(path: Path) -> dict[str, object]:
    cap = cv2.VideoCapture(str(path)); fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.); frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0); width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0); height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0); cap.release()
    audio = False
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try: audio = bool(subprocess.check_output([str(ffprobe), "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)], text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError): pass
    return {"width": width, "height": height, "resolution": f"{width}x{height}", "source_fps": fps, "frame_count": frames, "duration_sec": frames / fps if fps else 0., "has_audio_stream": audio, "extension": path.suffix.lower(), "size_bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--sample-size", type=int, default=24); args = parser.parse_args(); OUT.mkdir(parents=True, exist_ok=True)
    csv_path = DATA / "DF" / "df_videos.csv"; source = pd.read_csv(csv_path, encoding="utf-8-sig"); by_path = {str(row.ruta_video): row for row in source.itertuples(index=False)}; rows = []; used_paths = set()
    # Los IDs históricos son la posición 1-based del CSV y deben preservarse.
    for csv_index, row in enumerate(source.itertuples(index=False), 1):
        path = Path(str(row.ruta_video)); used_paths.add(str(path)); rows.append({"id_video": str(csv_index), "video": str(row.video), "ruta_video": str(path), "historical_class": str(row.clase), "historical_label": int(row.etiqueta)})
    for path in sorted(VIDEOS.glob("*.mp4")):
        if str(path) in used_paths: continue
        rows.append({"id_video": str(len(rows)+1), "video": path.name, "ruta_video": str(path), "historical_class": "unknown", "historical_label": None})
    inventory = pd.DataFrame(rows); inventory.to_csv(OUT / "video_inventory.csv", index=False, encoding="utf-8-sig")
    rng = random.Random(SEED); chosen = []
    # Mantiene los tres casos de estabilidad y después cubre las clases históricas.
    for stable_id in ("21", "126", "166"):
        match = inventory[inventory.id_video == stable_id]
        if not match.empty: chosen.append(match.iloc[0].to_dict())
    remaining = inventory[~inventory.id_video.isin({x["id_video"] for x in chosen})]
    quotas = {"Eliminacion": 7, "Eliminado": 5, "Victoria": 5, "unknown": max(0, args.sample_size - 3 - 17)}
    for label, quota in quotas.items():
        pool = remaining[remaining.historical_class == label].to_dict("records"); rng.shuffle(pool); chosen.extend(pool[:quota])
    if len(chosen) < args.sample_size:
        pool = [x for x in remaining.to_dict("records") if x["id_video"] not in {y["id_video"] for y in chosen}]; rng.shuffle(pool); chosen.extend(pool[:args.sample_size-len(chosen)])
    chosen = chosen[:args.sample_size]
    for item in chosen: item.update(probe(Path(item["ruta_video"])))
    sample = pd.DataFrame(chosen); sample.to_csv(OUT / "stratified_sample.csv", index=False, encoding="utf-8-sig")
    command, tessdata, diagnostics = resolve_tesseract(); tracked = [Path(__file__), ROOT / "backend" / "temporal_labeling" / "run_pipeline.py", ROOT / "backend" / "temporal_labeling" / "stability_report.py", ROOT / "backend" / "temporal_labeling" / "benchmark.py"]
    freeze = {"release": "temporal_detector_v0.3.0", "detector_version": VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "inventory_count": len(inventory), "csv_count": len(source), "unlisted_file_count": int((inventory.historical_class == "unknown").sum()), "sample_size": len(sample), "parameters": {"sample_fps": 1.0, "refine_fps": 12.0, "ocr_language": "eng+spa", "ocr_cache_modes": ["use", "ignore", "rebuild"], "regions": REGIONS, "text_patterns": TEXT_PATTERNS, "visual_gate": 0.34, "visual_change_threshold": 0.018, "fallback_max_representatives": 6, "safe_seek_margin_sec": 2.0}, "tesseract": {"command": command, "tessdata": str(tessdata) if tessdata else None, "diagnostics": diagnostics}, "executable_versions": executable_versions(), "file_hashes": {str(path): digest(path) for path in tracked if path.exists()}, "selection_criteria": "stable ids 21/126/166 plus fixed-seed quotas across historical classes and unknown files; historical class used only for diversity selection"}
    (OUT / "detector_freeze.json").write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"); (OUT / "selection_manifest.json").write_text(json.dumps({"seed": SEED, "criteria": freeze["selection_criteria"], "videos": sample.to_dict("records")}, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps({"inventory": len(inventory), "csv": len(source), "sample": len(sample), "output": str(OUT)}, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
