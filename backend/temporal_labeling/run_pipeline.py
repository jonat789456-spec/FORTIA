from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import pandas as pd

from dataclasses import asdict, fields

from detector import VERSION, detect_video, executable_versions

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite")
VIDEOS = DATA / "VIDEOS" / "ORIGINAL"
OUT = ROOT / "backend" / "data" / "automatic_temporal_annotations"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_rows() -> list[dict]:
    csv = DATA / "DF" / "df_videos.csv"
    if not csv.exists():
        return [{"id_video": str(index), "video": p.name, "ruta_video": str(p), "clase_historica": "unknown"} for index, p in enumerate(sorted(VIDEOS.glob("*")), 1)]
    frame = pd.read_csv(csv, encoding="utf-8-sig")
    return [{"id_video": str(index), "video": str(row.video), "ruta_video": str(row.ruta_video), "clase_historica": str(row.clase)} for index, row in enumerate(frame.itertuples(index=False), 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Etiquetado temporal automático reproducible; no modifica modelos ni datos originales.")
    parser.add_argument("--sample", action="store_true", help="procesa los videos 21, 126 y 166")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sample-fps", type=float, default=8.0)
    parser.add_argument("--refine-fps", type=float, default=12.0)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--ocr-cache", type=Path, default=None)
    parser.add_argument("--ocr-cache-mode", choices=("use", "ignore", "rebuild"), default="use")
    parser.add_argument("--ids-file", type=Path, default=None, help="CSV con columna id_video para una muestra congelada")
    parser.add_argument("--resume", action="store_true", help="reanuda desde checkpoint.jsonl sin repetir videos terminados")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    evidence = output / "evidence"
    evidence.mkdir(exist_ok=True)
    rows = video_rows()
    if args.sample:
        rows = [row for row in rows if row["id_video"] in {"21", "126", "166"}]
    elif args.ids_file:
        selected = set(pd.read_csv(args.ids_file)["id_video"].astype(str))
        rows = [row for row in rows if row["id_video"] in selected]
    elif args.limit:
        rows = rows[: args.limit]
    detections: list[dict] = []
    excluded: list[dict] = []
    summaries: list[dict] = []
    checkpoint = output / "checkpoint.jsonl"
    processed_ids: set[str] = set()
    if args.resume and checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            item = json.loads(line); processed_ids.add(str(item["id_video"])); summaries.append(item["summary"]); detections.extend(item.get("detections", [])); excluded.extend(item.get("excluded", []))
    elif checkpoint.exists():
        checkpoint.unlink()
    for row in rows:
        if row["id_video"] in processed_ids: continue
        path = Path(row["ruta_video"])
        if not path.exists():
            missing = {**row, "event_type": "ambiguous", "reason": "video_missing"}; excluded.append(missing)
            with checkpoint.open("a", encoding="utf-8") as stream: stream.write(json.dumps({"id_video": row["id_video"], "summary": {**row, "status": "failed", "error": "video_missing"}, "detections": [], "excluded": [missing]}, ensure_ascii=False) + "\n")
            continue
        cache_path = args.ocr_cache or (output / "ocr_cache.json")
        found, summary = detect_video(path, row["id_video"], args.sample_fps, refine_fps=args.refine_fps, evidence_dir=evidence / str(row["id_video"]), cache_path=cache_path, cache_mode=args.ocr_cache_mode)
        row_summary = {**row, **summary}; summaries.append(row_summary); row_detections = []; row_excluded = []
        for detection in found:
            record = asdict(detection)
            record["event_id"] = f"{row['id_video']}-{detection.event_type}-{detection.event_sequence_number}-{int(detection.event_time_sec * 1000)}"
            record["session_id"] = "unknown"
            record["session_confidence"] = 0.0
            record["session_id_source"] = "unknown"
            record["historical_label_secondary"] = row["clase_historica"]
            if detection.confidence_level == "high_confidence":
                detections.append(record); row_detections.append(record)
            else:
                excluded_record = {**record, "reason": detection.exclusion_reason or "not_high_confidence"}; excluded.append(excluded_record); row_excluded.append(excluded_record)
        with checkpoint.open("a", encoding="utf-8") as stream: stream.write(json.dumps({"id_video": row["id_video"], "summary": row_summary, "detections": row_detections, "excluded": row_excluded}, ensure_ascii=False) + "\n")
    detector_columns = [field.name for field in fields(__import__("detector").Detection)]
    event_columns = ["event_id", "id_video", "video_name", "video_path", "session_id", "session_confidence", "session_id_source"] + [field for field in detector_columns if field not in {"id_video", "video_name", "video_path"}] + ["historical_label_secondary"]
    excluded_columns = event_columns + ["reason"]
    events = pd.DataFrame(detections, columns=event_columns)
    excluded_frame = pd.DataFrame(excluded, columns=excluded_columns)
    for frame, name in ((events, "automatic_events"), (excluded_frame, "excluded_ambiguous_events")):
        frame.to_csv(output / f"{name}.csv", index=False, encoding="utf-8-sig")
        frame.to_parquet(output / f"{name}.parquet", index=False)
    events.to_json(output / "automatic_events.json", orient="records", force_ascii=False, indent=2)
    (output / "neutral_windows.csv").write_text("window_id,reason,status\n,No se generan Neutral sin detector de gameplay validado,excluded\n", encoding="utf-8")
    windows = [{"window_id": f"window-{item['event_id']}", "event_id": item["event_id"], "horizon_sec": 5.0, "status": "valid", "reason": "high_confidence_event"} for item in detections]
    pd.DataFrame(windows, columns=["window_id", "event_id", "horizon_sec", "status", "reason"]).to_csv(output / "predictive_windows_manifest.csv", index=False, encoding="utf-8")
    pd.DataFrame([{**row, "session_id": "unknown", "session_confidence": 0.0, "session_id_source": "unknown"} for row in rows]).to_csv(output / "session_inference_report.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(summaries).to_csv(output / "processing_errors.csv", index=False, encoding="utf-8-sig")
    summary = {"version": VERSION, "processed_at": datetime.now(timezone.utc).isoformat(), "test_used": False, "model_trained": False, "active_model_changed": False, "videos_requested": len(rows), "videos_processed": sum(1 for row in summaries if row.get("status") == "processed"), "videos_failed": len(rows) - len(summaries), "events_high_confidence": len(detections), "events_excluded": len(excluded), "events_by_type": dict(Counter(item["event_type"] for item in detections)), "excluded_by_reason": dict(Counter(item.get("reason", "unknown") for item in excluded)), "multiple_event_videos": sum(1 for row in summaries if row.get("detection_count", 0) > 1), "sessions_inferred": 0, "sessions_unknown": len(rows), "usable_fraction": (len(detections) / max(1, len(rows))), "sample_fps": args.sample_fps, "versions": executable_versions(), "source_hashes": {str(DATA / "DF" / "df_videos.csv"): file_hash(DATA / "DF" / "df_videos.csv")}}
    summary["refine_fps"] = args.refine_fps
    (output / "coverage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "consistency_report.json").write_text(json.dumps({"status": "not_ground_truth_accuracy", "sampled_configurations": [args.sample_fps], "low_confidence_excluded": True, "notes": ["Sin OCR instalado, las detecciones específicas no se aceptan como alta confianza.", "La etiqueta histórica solo se conserva como comprobación secundaria."]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "reproduction.md").write_text("# Reproducción\n\nDesde `backend/temporal_labeling`:\n\n```powershell\npython run_pipeline.py --sample\npython run_pipeline.py\n```\n\nEl pipeline requiere `opencv-python` y `pandas`. Para OCR opcional instala `pytesseract` y Tesseract OCR. Las detecciones solo se aceptan como `high_confidence` con señales OCR específicas persistentes; los demás casos se excluyen. No usa `test`, no entrena y no modifica los videos originales.\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
