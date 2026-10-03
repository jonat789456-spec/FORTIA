"""Audita videos, ventanas y archivos con la unidad F: disponible; nunca carga test para entrenar."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite")
DF = DATA / "DF"
OUT = ROOT / "backend" / "reports" / "data_audit_20261001"
CLASSES = ("Eliminado", "Eliminacion", "Victoria")


def count_by_split(df: pd.DataFrame, split: pd.DataFrame, name: str) -> dict[str, int]:
    merged = df[["id_video"]].merge(split[["id_video", "split", "clase"]], on="id_video", how="inner")
    return {f"{part}.{cls}": int(((merged["split"] == part) & (merged["clase"] == cls)).sum()) for part in ("train", "validation", "test", "excluded_ambiguous") for cls in CLASSES}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(ROOT / "backend/data/splits/video_split.csv", encoding="utf-8-sig")
    video_counts = {part: {cls: int(((split["split"] == part) & (split["clase"] == cls)).sum()) for cls in CLASSES} for part in ("train", "validation", "test", "excluded_ambiguous")}
    source_files = {
        "frames": (DF / "df_frames.csv", "ruta_imagen"),
        "health": (DF / "df_recortes_vida.csv", "ruta_vida"),
        "inventory": (DF / "df_recortes_inventario.csv", "ruta_inventario"),
        "map": (DF / "df_recortes_mapa.csv", "ruta_mapa"),
        "audio": (DF / "df_audio.csv", "ruta_espectrograma"),
    }
    windows: dict[str, dict[str, int]] = {}
    files: dict[str, dict[str, int]] = {}
    samples: dict[str, list[str]] = {}
    for modality, (path, column) in source_files.items():
        df = pd.read_csv(path, encoding="utf-8-sig")
        windows[modality] = count_by_split(df, split, modality)
        missing = 0
        corrupt = 0
        values = df[column].dropna().astype(str).tolist()
        for value in values:
            file_path = Path(value)
            if not file_path.exists():
                missing += 1
        for value in values[: min(20, len(values))]:
            file_path = Path(value)
            if file_path.exists() and file_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                try:
                    with Image.open(file_path) as image:
                        image.verify()
                except (OSError, ValueError):
                    corrupt += 1
        files[modality] = {"rows": int(len(df)), "uniqueVideos": int(df["id_video"].nunique()), "duplicateRowsByVideo": int(len(df) - df["id_video"].nunique()), "missing": missing, "corrupt": corrupt, "corruptCheckSampleRows": min(20, len(values))}
        samples[modality] = [str(value) for value in df[column].dropna().head(3)]
    groups = split.groupby("id_video")["split"].nunique()
    leakage = split[split["id_video"].duplicated(keep=False)].sort_values("id_video")
    report = {"dataRoot": str(DATA), "testEvaluated": False, "videoCounts": video_counts, "windowCounts": windows, "files": files, "samplePaths": samples, "videoIdsWithMultipleSplits": [int(value) for value in groups[groups > 1].index], "duplicateVideoRows": int(split["id_video"].duplicated().sum()), "manifestRows": int(len(split)), "notes": ["Las ventanas repiten id_video por diseño temporal; la unidad de split es video.", "La carpeta test solo se contabiliza por metadata; no se cargaron sus muestras para entrenamiento, calibración o selección."]}
    (OUT / "DATA_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    leakage.to_csv(OUT / "split_leakage_rows.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({"report": str(OUT / "DATA_AUDIT.json"), "leakageVideos": report["videoIdsWithMultipleSplits"], "testEvaluated": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
