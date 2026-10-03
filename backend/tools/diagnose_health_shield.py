"""Guarda captura, ROI y máscaras HSV para calibrar el HUD de Fortnite."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.preprocessing.structured import HealthShieldReader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, default=Path("backend/reports/health_shield_diagnostics"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    full = np.asarray(Image.open(args.image).convert("RGB"))
    height, width = full.shape[:2]
    left, right = int(width * 0.0), int(width * 489 / 1360)
    top, bottom = int(height * 552 / 768), height
    crop = full[top:bottom, left:right]
    reader = HealthShieldReader(diagnostics=True)
    result = reader.read_debug(crop, timestamp=0.0)
    Image.fromarray(full).save(args.output / "capture_full.png")
    Image.fromarray(crop).save(args.output / "hud_roi.png")
    draw = Image.fromarray(full.copy())
    ImageDraw.Draw(draw).rectangle((left, top, right, bottom), outline=(255, 220, 30), width=max(2, width // 700))
    draw.save(args.output / "capture_roi_overlay.png")
    rgb = crop.astype(np.float32)
    maximum, minimum = rgb.max(axis=2), rgb.min(axis=2)
    saturation = maximum - minimum
    visible = ((saturation / np.maximum(maximum, 1) > 0.28) & (maximum / 255 > 0.22)).astype(np.uint8) * 255
    Image.fromarray(visible).save(args.output / "mask_saturation.png")
    (args.output / "diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "imageShape": [height, width], "reading": result["reading"], "test_used": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
