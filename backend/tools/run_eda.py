"""Genera EDA reproducible a partir de los CSV y manifiestos auditados."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
OUT = ROOT / "backend" / "reports" / "eda"
MANIFEST = ROOT / "backend" / "data" / "manifests"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DF_ROOT / name, encoding="utf-8-sig")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    videos = read_csv("df_videos.csv")
    audio = read_csv("df_audio.csv")
    frames = read_csv("df_frames.csv")
    health = read_csv("df_recortes_vida.csv")
    inventory = read_csv("df_recortes_inventario.csv")
    map_df = read_csv("df_recortes_mapa.csv")
    manifest = pd.read_csv(MANIFEST / "file_manifest.csv", encoding="utf-8-sig")
    matrix = pd.read_csv(MANIFEST / "modality_matrix.csv", encoding="utf-8-sig")

    class_counts = videos.groupby(["clase", "etiqueta"], dropna=False).size().reset_index(name="videos")
    class_counts.to_csv(OUT / "class_distribution.csv", index=False, encoding="utf-8-sig")

    duration = health.groupby("id_video", as_index=False).agg(duration_sec=("duracion_video_seg", "first"), fps=("fps", "first"), width=("ancho_original", "first"), height=("alto_original", "first"))
    duration = duration.merge(videos[["video", "clase", "etiqueta"]].reset_index(names="id_video"), on="id_video", how="left")
    duration.to_csv(OUT / "video_numeric_profile.csv", index=False, encoding="utf-8-sig")

    audio_profile = audio[["id_video", "duracion_audio_seg", "frecuencia_muestreo", "estado_audio", "clase", "etiqueta"]]
    audio_profile.to_csv(OUT / "audio_profile.csv", index=False, encoding="utf-8-sig")

    modality_counts = pd.DataFrame({
        "modality": ["original_video", "frames", "health", "inventory", "map", "audio"],
        "available_ids": [int(matrix[column].sum()) for column in ["original_video_available", "frames_available", "health_available", "inventory_available", "map_available", "audio_available"]],
    })
    modality_counts.to_csv(OUT / "modality_availability.csv", index=False, encoding="utf-8-sig")

    numeric_summary = duration[["duration_sec", "fps", "width", "height"]].describe().T
    numeric_summary.to_csv(OUT / "numeric_summary.csv", encoding="utf-8-sig")
    modality_image_summary = manifest[manifest["modality"].isin(["frames", "health", "inventory", "map", "audio"])].groupby("modality").agg(
        files=("path", "count"), corrupt=("integrity", lambda values: int((values == "corrupt").sum())),
        min_width=("width", "min"), max_width=("width", "max"), min_height=("height", "min"), max_height=("height", "max"),
    ).reset_index()
    modality_image_summary.to_csv(OUT / "image_quality_summary.csv", index=False, encoding="utf-8-sig")

    plots = []
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(class_counts["clase"].astype(str), class_counts["videos"], color=["#ef4444", "#3b82f6", "#22c55e"])
    ax.set_title("Videos por clase")
    ax.set_ylabel("Videos")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    class_plot = OUT / "class_distribution.png"
    fig.savefig(class_plot, dpi=140)
    plt.close(fig)
    plots.append(class_plot.name)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(duration["duration_sec"].dropna(), bins=20, color="#6366f1", edgecolor="white")
    ax.set_title("Distribución de duración de videos")
    ax.set_xlabel("Duración (s)")
    ax.set_ylabel("Videos")
    fig.tight_layout()
    duration_plot = OUT / "duration_distribution.png"
    fig.savefig(duration_plot, dpi=140)
    plt.close(fig)
    plots.append(duration_plot.name)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(modality_counts["modality"], modality_counts["available_ids"], color="#14b8a6")
    ax.set_title("Disponibilidad por modalidad")
    ax.set_ylabel("ID de video")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    modality_plot = OUT / "modality_availability.png"
    fig.savefig(modality_plot, dpi=140)
    plt.close(fig)
    plots.append(modality_plot.name)

    summary = {
        "videos": int(len(videos)),
        "classes": class_counts.to_dict(orient="records"),
        "duration_sec": {"min": float(duration.duration_sec.min()), "max": float(duration.duration_sec.max()), "median": float(duration.duration_sec.median())},
        "fps": sorted(duration.fps.dropna().unique().tolist()),
        "resolutions": sorted({f"{int(row.width)}x{int(row.height)}" for row in duration[["width", "height"]].dropna().itertuples(index=False)}),
        "audio_sample_rates": sorted(audio.frecuencia_muestreo.dropna().unique().tolist()),
        "plots": plots,
        "notes": ["El EDA usa df_videos.csv como fuente canónica de clases.", "La disponibilidad de audio corresponde a espectrogramas PNG, no a audio crudo."],
    }
    (OUT / "eda_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        "# Reporte EDA",
        "",
        f"Videos analizados: **{len(videos)}**",
        "",
        "## Distribución de clases",
        "",
        class_counts.to_markdown(index=False),
        "",
        "## Perfil numérico",
        "",
        numeric_summary.to_markdown(),
        "",
        "## Calidad por modalidad",
        "",
        modality_image_summary.to_markdown(index=False),
        "",
        "## Observaciones",
        "",
        "- Las modalidades tienen disponibilidad para los 751 `id_video` según la matriz auditada.",
        "- `Victoria` tiene 21 videos y debe evaluarse con validación agrupada y cautela.",
        "- Los gráficos se encuentran en este mismo directorio.",
    ]
    (OUT / "EDA_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "plots": plots}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
