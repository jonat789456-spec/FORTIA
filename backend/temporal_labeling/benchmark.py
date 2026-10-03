"""Benchmark reproducible del detector temporal sobre uno o varios videos."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from detector import detect_video


def memory_mb() -> float:
    try:
        import psutil  # type: ignore
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--video", type=Path, action="append", required=True); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--sample-fps", type=float, default=1.); parser.add_argument("--refine-fps", type=float, default=12.); parser.add_argument("--cache-mode", choices=("use", "ignore", "rebuild"), default="ignore")
    args = parser.parse_args(); rows = []
    for number, video in enumerate(args.video, 1):
        started = time.perf_counter(); before = memory_mb(); detections, summary = detect_video(video, str(number), args.sample_fps, args.refine_fps, args.output / f"evidence_{number}", args.output / "ocr_cache.json", args.cache_mode); after = memory_mb()
        rows.append({"video": str(video), "elapsed_sec": time.perf_counter()-started, "memory_before_mb": before, "memory_after_mb": after, "detections": len(detections), "summary": summary})
    result = {"version": "benchmark-0.3.0", "configuration": {"sample_fps": args.sample_fps, "refine_fps": args.refine_fps, "cache_mode": args.cache_mode}, "videos": rows}; args.output.mkdir(parents=True, exist_ok=True); (args.output / "benchmark.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
