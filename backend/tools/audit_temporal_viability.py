"""Evalúa si los manifests existentes permiten construir etiquetas temporales sin inventar eventos."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite")
DF = DATA / "DF"
OUT = ROOT / "backend" / "reports" / "temporal_viability_20261001"
CLASSES = ("Eliminado", "Eliminacion", "Victoria")
SAMPLE_IDS = {"Eliminado": 126, "Eliminacion": 21, "Victoria": 166}


def make_contact_sheet(rows: list[dict[str, object]], output: Path) -> None:
    tiles: list[Image.Image] = []
    labels: list[str] = []
    for row in rows:
        path = Path(str(row["path"]))
        with Image.open(path) as image:
            tile = image.convert("RGB").resize((480, 270))
        canvas = Image.new("RGB", (480, 300), "#111827")
        canvas.paste(tile, (0, 0))
        ImageDraw.Draw(canvas).text((8, 278), f"{row['class']} · video {row['id_video']} · t={row['timestamp_sec']}s", fill="white")
        tiles.append(canvas)
        labels.append(str(row["class"]))
    sheet = Image.new("RGB", (960, ((len(tiles) + 1) // 2) * 300), "#030712")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % 2) * 480, (index // 2) * 300))
    sheet.save(output, quality=90)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    split = pd.read_csv(ROOT / "backend/data/splits/video_split.csv", encoding="utf-8-sig")
    frames = pd.read_csv(DF / "df_frames.csv", encoding="utf-8-sig")
    life = pd.read_csv(DF / "df_recortes_vida.csv", encoding="utf-8-sig")
    audio = pd.read_csv(DF / "df_audio.csv", encoding="utf-8-sig")
    available_columns = sorted(set(split.columns) | set(frames.columns) | set(life.columns) | set(audio.columns))
    event_columns = [column for column in available_columns if any(token in column.casefold() for token in ("event", "evento", "session", "sesion", "timestamp"))]
    sample_rows: list[dict[str, object]] = []
    for class_name, video_id in SAMPLE_IDS.items():
        selected = frames[frames["id_video"] == video_id].sort_values("tiempo_seg")
        for row in selected.itertuples():
            sample_rows.append({"id_video": int(video_id), "group_id": int(split.loc[split.id_video == video_id, "group_id"].iloc[0]), "split": str(split.loc[split.id_video == video_id, "split"].iloc[0]), "class": class_name, "timestamp_sec": float(row.tiempo_seg), "event_time_sec": None, "horizon_sec": None, "window_type": "unassignable", "path": str(row.ruta_imagen), "reason": "missing_event_time_sec"})
    pd.DataFrame(sample_rows).to_csv(OUT / "temporal_sample_manifest.csv", index=False, encoding="utf-8-sig")
    make_contact_sheet(sample_rows, OUT / "temporal_sample_contact_sheet.jpg")
    report = {"version": "temporal-viability-20261001", "dataRoot": str(DATA), "testUsed": False, "canTrainTemporal": False, "sampleVideos": SAMPLE_IDS, "availableEventRelatedColumns": event_columns, "missingRequiredFields": ["event_time_sec", "session_id"], "availableTiming": {"frameTimestamp": "df_frames.tiempo_seg", "structuredTimestamp": "df_recortes_vida.tiempo_seg", "clipDuration": "df_recortes_vida.duracion_video_seg", "audioDuration": "df_audio.duracion_audio_seg"}, "proposedHorizons": ["0-3", "3-5", "5-10"], "sampleRows": len(sample_rows), "sampleStatus": "blocked_missing_event_time_sec", "visualReview": {"contactSheet": str(OUT / "temporal_sample_contact_sheet.jpg"), "observations": ["Las muestras pueden contener overlays finales según la clase.", "Sin event_time_sec no se puede demostrar que una ventana sea anterior al evento.", "El final del clip no se acepta como timestamp real del evento."]}, "requiredNextData": ["event_time_sec anotado por video o sesión", "session_id o partida", "criterio de confirmación del evento", "timestamps sincronizados para audio y video", "anotaciones de ventanas ambiguas"]}
    (OUT / "TEMPORAL_VIABILITY_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "TEMPORAL_VIABILITY_REPORT.md").write_text("# Viabilidad temporal — 2026-10-01\n\nLa construcción temporal queda bloqueada: los manifests no contienen `event_time_sec` ni `session_id`. Se generó una muestra auditable, pero ninguna fila se considera entrenable. El final del clip no se utiliza como proxy.\n\n## Horizontes propuestos\n\n`0–3`, `3–5` y `5–10` segundos antes del evento, sujetos a timestamps anotados.\n\n## Entregables\n\n- `temporal_sample_manifest.csv`: muestra con `event_time_sec` nulo y motivo de exclusión.\n- `temporal_sample_contact_sheet.jpg`: revisión visual reproducible de las muestras 126, 21 y 166 de validation.\n- `TEMPORAL_VIABILITY_REPORT.json`: campos disponibles y datos faltantes.\n\nNo se entrenó, calibró ni seleccionó ningún modelo temporal. `test` permanece sellado.\n", encoding="utf-8")
    print(json.dumps({"report": str(OUT / "TEMPORAL_VIABILITY_REPORT.json"), "canTrainTemporal": False, "missing": report["missingRequiredFields"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
