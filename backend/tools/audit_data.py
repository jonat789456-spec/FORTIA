"""Auditoría reproducible y de solo lectura del dataset de Fortnite IA.

Este script no modifica ninguna ruta de datos de F:. Solo escribe resultados
derivados dentro de backend/reports/audit y backend/data/manifests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEOS = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS")
DEFAULT_DF = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}


def json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_data_path(value: str, videos_root: Path, df_root: Path) -> Path:
    raw = Path(str(value).strip())
    if raw.exists():
        return raw
    text = str(value).replace("/", "\\")
    for root in (videos_root, df_root):
        marker = "\\VIDEOS\\" if "\\VIDEOS\\" in text.upper() else "\\DF\\" if "\\DF\\" in text.upper() else None
        if marker:
            suffix = text.upper().split(marker, 1)[1]
            candidate = root / Path(suffix)
            if candidate.exists():
                return candidate
    return raw


def run_ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-of", "json",
        "-show_entries", "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,channels,sample_rate",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode != 0:
            return {"probe_status": "error", "probe_error": completed.stderr.strip()[:500]}
        payload = json.loads(completed.stdout or "{}")
        streams = payload.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
        return {
            "probe_status": "ok",
            "duration_sec": float(payload.get("format", {}).get("duration")) if payload.get("format", {}).get("duration") else None,
            "video_codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
            "audio_codec": audio.get("codec_name"),
            "audio_channels": audio.get("channels"),
            "audio_sample_rate": audio.get("sample_rate"),
        }
    except Exception as exc:  # noqa: BLE001 - el reporte debe continuar con otros archivos
        return {"probe_status": "error", "probe_error": str(exc)[:500]}


def inspect_image(path: Path) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            extrema = image.convert("L").getextrema()
            return {
                "integrity": "ok",
                "width": image.width,
                "height": image.height,
                "channels": len(image.getbands()),
                "mode": image.mode,
                "format": image.format,
                "is_blank": extrema[0] == extrema[1],
                "is_dark": extrema[1] <= 10,
            }
    except Exception as exc:  # noqa: BLE001 - la corrupción es un resultado de auditoría
        return {"integrity": "corrupt", "error": str(exc)[:500]}


def classify_filename(name: str) -> tuple[str, str]:
    normalized = name.casefold()
    if "victoria" in normalized:
        return "Victoria", "explicit_victory"
    if "eliminado" in normalized:
        return "Eliminado", "explicit_eliminated"
    if any(token in normalized for token in ("eliminación", "eliminacion")):
        return "Eliminacion", "elimination_variant"
    if "abajo" in normalized:
        return "unknown", "ambiguous_abajo"
    return "unknown", "no_rule"


def discover_modality_folders(videos_root: Path) -> dict[str, str | None]:
    expected = {
        "frames": ("frame", "fram"),
        "audio": ("audio", "audios"),
        "inventory": ("inventario", "inventory"),
        "map": ("mapa", "map"),
        "original": ("original", "origunal", "origunal"),
        "health": ("vida", "health"),
    }
    folders = [item for item in videos_root.iterdir() if item.is_dir()]
    result: dict[str, str | None] = {}
    for modality, tokens in expected.items():
        match = next((item for item in folders if item.name.casefold() in tokens), None)
        if match is None:
            match = next((item for item in folders if any(token in item.name.casefold() for token in tokens)), None)
        result[modality] = match.name if match else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos-root", type=Path, default=DEFAULT_VIDEOS)
    parser.add_argument("--df-root", type=Path, default=DEFAULT_DF)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    videos_root = args.videos_root.resolve()
    df_root = args.df_root.resolve()
    project_root = args.project_root.resolve()
    report_root = project_root / "backend" / "reports" / "audit"
    manifest_root = project_root / "backend" / "data" / "manifests"
    report_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    folders = discover_modality_folders(videos_root)
    all_files = [item for item in videos_root.rglob("*") if item.is_file()]
    folder_summary = []
    for folder in sorted([item for item in videos_root.iterdir() if item.is_dir()]):
        files = [item for item in folder.rglob("*") if item.is_file()]
        extension_counts = Counter(item.suffix.casefold() for item in files)
        folder_summary.append({
            "folder": folder.name,
            "file_count": len(files),
            "bytes": sum(item.stat().st_size for item in files),
            "extensions": dict(sorted(extension_counts.items())),
        })

    dataframe_summary: dict[str, Any] = {}
    dataframe_rows: dict[str, pd.DataFrame] = {}
    for csv_path in sorted(df_root.glob("*.csv")):
        try:
            frame = pd.read_csv(csv_path, encoding="utf-8-sig")
            dataframe_rows[csv_path.name] = frame
            dataframe_summary[csv_path.name] = {
                "rows": int(len(frame)),
                "columns": list(frame.columns),
                "dtypes": {key: str(value) for key, value in frame.dtypes.items()},
                "missing_by_column": {key: int(value) for key, value in frame.isna().sum().items()},
                "duplicate_rows": int(frame.duplicated().sum()),
                "class_counts": frame["clase"].value_counts(dropna=False).to_dict() if "clase" in frame else {},
                "path_columns": {
                    key: {
                        "values": int(frame[key].notna().sum()),
                        "missing_files": int(sum(not resolve_data_path(value, videos_root, df_root).exists() for value in frame[key].dropna().astype(str))),
                    }
                    for key in frame.columns if any(token in key.casefold() for token in ("ruta", "path"))
                },
            }
        except Exception as exc:  # noqa: BLE001
            dataframe_summary[csv_path.name] = {"error": str(exc)}

    video_df = dataframe_rows.get("df_videos.csv", pd.DataFrame())
    classification_df = dataframe_rows.get("df_clasificacion.csv", pd.DataFrame())
    labels_from_video = {
        str(row.video): {"id_video": index + 1, "class": row.clase, "code": row.etiqueta, "path": row.ruta_video}
        for index, row in video_df.iterrows()
    }
    original_video_ids = {
        index + 1
        for index, row in video_df.iterrows()
        if resolve_data_path(row.ruta_video, videos_root, df_root).exists()
    }

    file_rows: list[dict[str, Any]] = []
    modality_ids: dict[str, set[int]] = defaultdict(set)
    duplicate_size_candidates: dict[int, list[str]] = defaultdict(list)

    def inspect_file(path: Path) -> dict[str, Any]:
        relative = path.relative_to(videos_root)
        match = re.search(r"video[_-]?(\d+)", path.as_posix(), flags=re.IGNORECASE)
        id_video = int(match.group(1)) if match else None
        top_folder = relative.parts[0] if relative.parts else ""
        modality = next((key for key, folder in folders.items() if folder == top_folder), "unknown")
        if id_video is not None and modality != "unknown":
            modality_ids[modality].add(id_video)
        row: dict[str, Any] = {
            "path": str(path),
            "relative_path": str(relative),
            "folder": top_folder,
            "modality": modality,
            "id_video": id_video,
            "extension": path.suffix.casefold(),
            "bytes": path.stat().st_size,
        }
        if path.suffix.casefold() in IMAGE_EXTENSIONS:
            row.update(inspect_image(path))
        elif path.suffix.casefold() in VIDEO_EXTENSIONS:
            row.update(run_ffprobe(path))
        else:
            row["integrity"] = "not_inspected"
        return row

    # Las validaciones son independientes por archivo. El paralelismo reduce
    # el tiempo de espera de la unidad de datos sin modificar sus contenidos.
    with ThreadPoolExecutor(max_workers=8) as executor:
        file_rows = list(executor.map(inspect_file, all_files))
    for row in file_rows:
        if row.get("bytes", 0) > 0 and row.get("integrity") == "ok":
            # Solo se calcula SHA-256 cuando al menos dos archivos comparten
            # tamaño; esto conserva la detección exacta y evita leer de nuevo
            # todos los archivos únicos de la unidad F:.
            duplicate_size_candidates[row["bytes"]].append(row["path"])

    image_or_video_rows = pd.DataFrame(file_rows)
    image_or_video_rows.to_csv(manifest_root / "file_manifest.csv", index=False, encoding="utf-8-sig")
    duplicate_digest_candidates: dict[tuple[int, str], list[str]] = defaultdict(list)
    for size, paths in duplicate_size_candidates.items():
        if len(paths) < 2:
            continue
        for path_text in paths:
            digest = sha256(Path(path_text))
            duplicate_digest_candidates[(size, digest)].append(path_text)
    duplicate_rows = [
        {"size": size, "sha256": digest, "paths": json.dumps(paths, ensure_ascii=False), "count": len(paths)}
        for (size, digest), paths in duplicate_digest_candidates.items() if len(paths) > 1
    ]
    pd.DataFrame(duplicate_rows).to_csv(manifest_root / "duplicate_groups.csv", index=False, encoding="utf-8-sig")

    modality_map = {
        "original_video": original_video_ids,
        "frames": modality_ids.get("frames", set()),
        "health": modality_ids.get("health", set()),
        "inventory": modality_ids.get("inventory", set()),
        "map": modality_ids.get("map", set()),
        "audio": modality_ids.get("audio", set()),
    }
    all_ids = sorted(set().union(*modality_map.values()) if modality_map else set())
    matrix_rows = []
    for id_video in all_ids:
        row = {"id_video": id_video}
        for modality, ids in modality_map.items():
            row[f"{modality}_available"] = id_video in ids
        source = next((item for item in labels_from_video.values() if item["id_video"] == id_video), None)
        row["class_from_df_videos"] = source["class"] if source else None
        row["code_from_df_videos"] = source["code"] if source else None
        row["original_path"] = source["path"] if source else None
        matrix_rows.append(row)
    matrix = pd.DataFrame(matrix_rows)
    matrix.to_csv(manifest_root / "modality_matrix.csv", index=False, encoding="utf-8-sig")

    filename_labels = Counter()
    filename_rules = Counter()
    for path in all_files:
        if path.suffix.casefold() in VIDEO_EXTENSIONS:
            label, rule = classify_filename(path.name)
            filename_labels[label] += 1
            filename_rules[rule] += 1

    class_distributions = {
        name: frame["clase"].value_counts(dropna=False).to_dict()
        for name, frame in dataframe_rows.items() if "clase" in frame.columns
    }
    summary = {
        "generated_at": generated_at,
        "source_roots": {"videos": str(videos_root), "dataframes": str(df_root)},
        "project_root": str(project_root),
        "folders_detected": folders,
        "folder_summary": folder_summary,
        "total_files": len(all_files),
        "total_bytes": sum(item.stat().st_size for item in all_files),
        "dataframes": dataframe_summary,
        "class_distributions": class_distributions,
        "filename_class_rules": {"counts": dict(filename_labels), "rules": dict(filename_rules)},
        "modality_unique_ids": {key: len(value) for key, value in modality_map.items()},
        "matrix_rows": len(matrix),
        "image_corrupt_count": int((image_or_video_rows.get("integrity") == "corrupt").sum()) if not image_or_video_rows.empty else 0,
        "probe_error_count": int((image_or_video_rows.get("probe_status") == "error").sum()) if not image_or_video_rows.empty else 0,
        "exact_duplicate_groups": len(duplicate_rows),
        "original_png_count": sum(1 for item in all_files if item.parent.name.casefold() == folders.get("original", "").casefold() and item.suffix.casefold() == ".png"),
    }
    write_json(report_root / "audit_summary.json", summary)
    write_json(report_root / "dataframe_summary.json", dataframe_summary)

    report = [
        "# Reporte de auditoría de datos",
        "",
        f"Generado: `{generated_at}`",
        "",
        "## Alcance",
        "",
        "Auditoría de solo lectura. Las fuentes originales no fueron modificadas.",
        "",
        f"- Videos root: `{videos_root}`",
        f"- DataFrames root: `{df_root}`",
        f"- Archivos inspeccionados: **{len(all_files)}**",
        f"- Bytes inspeccionados: **{summary['total_bytes']:,}**",
        "",
        "## Carpetas detectadas",
        "",
        "| Modalidad | Carpeta real | IDs únicos |",
        "|---|---|---:|",
    ]
    for modality, folder in folders.items():
        report.append(f"| {modality} | `{folder or 'NO ENCONTRADA'}` | {summary['modality_unique_ids'].get(modality if modality != 'original' else 'original_video', 0)} |")
    report.extend([
        "",
        "## Clases por DataFrame",
        "",
        "```json",
        json.dumps(class_distributions, ensure_ascii=False, indent=2, default=json_default),
        "```",
        "",
        "## Reglas de nombres",
        "",
        "```json",
        json.dumps(summary["filename_class_rules"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Calidad preliminar",
        "",
        f"- Imágenes corruptas: **{summary['image_corrupt_count']}**",
        f"- Videos con error de ffprobe: **{summary['probe_error_count']}**",
        f"- Grupos de duplicados exactos: **{summary['exact_duplicate_groups']}**",
        f"- PNG dentro de ORIGINAL: **{summary['original_png_count']}**",
        "",
        "## Archivos generados",
        "",
        "- `backend/reports/audit/audit_summary.json`",
        "- `backend/reports/audit/dataframe_summary.json`",
        "- `backend/data/manifests/file_manifest.csv`",
        "- `backend/data/manifests/modality_matrix.csv`",
        "- `backend/data/manifests/duplicate_groups.csv`",
        "",
        "## Dictamen",
        "",
        "Las etiquetas y la suficiencia de las clases deben validarse antes del entrenamiento. "
        "Este reporte no autoriza por sí mismo el entrenamiento y debe complementarse con revisión de inconsistencias entre DataFrames.",
        "",
    ])
    (report_root / "audit_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"summary": str(report_root / "audit_summary.json"), "matrix": str(manifest_root / "modality_matrix.csv"), "files": len(all_files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
