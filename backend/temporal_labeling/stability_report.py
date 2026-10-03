"""Compara dos ejecuciones aisladas del mismo sample sin usar truth externo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


KEYS = ["id_video", "event_type", "event_sequence_number"]
FIELDS = ["event_time_sec", "event_frame", "frame_pts", "confidence_level", "acceptance_rule", "ocr_text_normalized", "visual_evidence"]


def load_events(folder: Path) -> pd.DataFrame:
    paths = [folder / "automatic_events.csv", folder / "excluded_ambiguous_events.csv"]
    frames = [pd.read_csv(path) for path in paths if path.exists()]
    if not frames:
        return pd.DataFrame(columns=KEYS + FIELDS + ["source_fps", "ocr_analysis_fps"])
    frame = pd.concat(frames, ignore_index=True)
    for key in KEYS:
        if key not in frame: frame[key] = ""
    return frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    left, right = load_events(args.run_a), load_events(args.run_b)
    left["_key"] = left[KEYS].astype(str).agg("|".join, axis=1); right["_key"] = right[KEYS].astype(str).agg("|".join, axis=1)
    all_keys = sorted(set(left["_key"]) | set(right["_key"])); rows = []
    for key in all_keys:
        a = left[left._key == key].iloc[0] if not left[left._key == key].empty else None
        b = right[right._key == key].iloc[0] if not right[right._key == key].empty else None
        if a is None or b is None:
            rows.append({"event_key": key, "stable": False, "reason": "event_missing_in_one_run"}); continue
        source_fps = max(float(a.get("source_fps", 0) or 0), float(b.get("source_fps", 0) or 0), 1.0)
        ocr_fps = max(float(a.get("ocr_analysis_fps", 0) or 0), float(b.get("ocr_analysis_fps", 0) or 0), 1.0)
        tolerance = max(1.0 / source_fps, 1.0 / ocr_fps)
        delta = abs(float(a.event_time_sec) - float(b.event_time_sec)); equal = all(str(a.get(field, "")) == str(b.get(field, "")) for field in FIELDS[1:])
        rows.append({"event_key": key, "stable": bool(delta <= tolerance and equal), "time_a": float(a.event_time_sec), "time_b": float(b.event_time_sec), "delta_sec": delta, "tolerance_sec": tolerance, "same_type": str(a.event_type) == str(b.event_type), "same_event_count_key": True, "same_confidence": str(a.confidence_level) == str(b.confidence_level), "same_acceptance_rule": str(a.acceptance_rule) == str(b.acceptance_rule), "same_ocr": str(a.ocr_text_normalized) == str(b.ocr_text_normalized), "same_visual_evidence": str(a.visual_evidence) == str(b.visual_evidence)})
    result = {"status": "stable" if all(row["stable"] for row in rows) else "unstable", "runs": [str(args.run_a), str(args.run_b)], "tolerance_definition": "max(1/source_fps, 1/ocr_analysis_fps)", "events": rows, "event_count_a": len(left), "event_count_b": len(right)}
    output = args.output or args.run_a.parent / "stability_report.json"; output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0 if result["status"] == "stable" else 1


if __name__ == "__main__": raise SystemExit(main())
