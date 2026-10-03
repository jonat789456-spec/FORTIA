from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

EVENT_TYPES = {"player_eliminated", "opponent_eliminated", "victory_confirmed"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--sample", type=Path, required=True); parser.add_argument("--run", type=Path, required=True); parser.add_argument("--freeze", type=Path, required=True); args = parser.parse_args()
    sample = pd.read_csv(args.sample); run = args.run; errors = []; events = pd.read_csv(run / "automatic_events.csv", encoding="utf-8-sig"); excluded = pd.read_csv(run / "excluded_ambiguous_events.csv", encoding="utf-8-sig")
    summary = json.loads((run / "coverage_summary.json").read_text(encoding="utf-8")); freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    if len(sample) < 15 or len(sample) > 30: errors.append("sample_size_out_of_range")
    if summary.get("videos_processed") != len(sample): errors.append("not_all_sample_videos_processed")
    if summary.get("version") != freeze.get("detector_version"): errors.append("detector_version_mismatch")
    for _, row in events.iterrows():
        if row.event_type not in EVENT_TYPES: errors.append(f"invalid_event_type:{row.event_id}")
        if row.confidence_level != "high_confidence": errors.append(f"non_high_confidence_event:{row.event_id}")
        if not bool(row.native_frame_observed): errors.append(f"non_native_event:{row.event_id}")
        if str(row.refinement_rule) == "native_frames_without_event_specific_evidence": errors.append(f"no_native_observation_rule:{row.event_id}")
        for field in ("evidence_visual_path", "evidence_region_path", "evidence_manifest_path"):
            if not Path(str(row[field])).exists(): errors.append(f"missing_evidence:{row.event_id}:{field}")
    gate = not errors and len(events) > 0 and len(excluded) >= 0
    result = {"valid": gate, "quality_gate": "pass" if gate else "fail", "sample_size": len(sample), "processed": summary.get("videos_processed"), "events_high_confidence": len(events), "events_excluded": len(excluded), "coverage_fraction": len(events) / max(1, len(sample)), "class_distribution": sample.historical_class.value_counts().to_dict(), "errors": errors, "training_ready": False, "test_used": False, "active_model_changed": False, "detector_version": freeze.get("release")}
    (run / "sample_validation_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0 if gate else 1


if __name__ == "__main__": raise SystemExit(main())
