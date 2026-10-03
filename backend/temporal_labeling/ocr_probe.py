from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from detector import match_event, optional_ocr, resolve_tesseract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--times", nargs="+", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    command, tessdata, diagnostics = resolve_tesseract()
    rows = []
    cap = cv2.VideoCapture(str(args.video))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    for time_sec in args.times:
        cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000.0)
        ok, frame = cap.read()
        if not ok:
            rows.append({"time_sec": time_sec, "status": "frame_unavailable"})
            continue
        text, confidence, method = optional_ocr(frame)
        event_type, score, signal = match_event(text)
        frame_path = args.output / f"frame_{time_sec:.2f}.jpg"
        cv2.imwrite(str(frame_path), frame)
        rows.append({"time_sec": time_sec, "frame": int(round(time_sec * fps)), "frame_path": str(frame_path), "text": text, "confidence": confidence, "event_type": event_type, "match_score": score, "signal": signal, "method": method})
    cap.release()
    (args.output / "ocr_diagnostics.json").write_text(json.dumps({"video": str(args.video), "tesseract": diagnostics, "tessdata": str(tessdata) if tessdata else None, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"video": str(args.video), "tesseract": diagnostics, "rows": rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
