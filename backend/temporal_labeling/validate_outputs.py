from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "data" / "automatic_temporal_annotations"
EVENT_TYPES = {"player_eliminated", "opponent_eliminated", "victory_confirmed"}


def main() -> int:
    events = pd.read_csv(OUT / "automatic_events.csv", encoding="utf-8-sig")
    errors: list[dict[str, object]] = []
    if not events.empty:
        for _, row in events.iterrows():
            if row.event_type not in EVENT_TYPES:
                errors.append({"event_id": row.event_id, "error": "invalid_event_type"})
            if not 0 <= float(row.event_time_sec):
                errors.append({"event_id": row.event_id, "error": "negative_time"})
            if row.confidence_level != "high_confidence":
                errors.append({"event_id": row.event_id, "error": "non_high_confidence_in_training_file"})
        duplicated = events[events.event_id.duplicated(keep=False)]
        errors.extend({"event_id": event_id, "error": "duplicate_event_id"} for event_id in duplicated.event_id.unique())
    output = {"valid": not errors, "event_count": int(len(events)), "errors": errors, "test_used": False, "active_model_changed": False}
    (OUT / "validation_report.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
