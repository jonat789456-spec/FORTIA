"""Valida las fuentes de etiquetas sin modificar los CSV originales."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DF_ROOT = Path(r"F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF")
OUT_ROOT = ROOT / "backend" / "reports" / "audit"
DOC_ROOT = ROOT / "backend" / "docs"


def normalize(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value)).casefold().strip()
    return "".join(char for char in normalized if not unicodedata.combining(char))


def filename_rule(filename: str) -> tuple[str, str]:
    value = normalize(filename)
    if "victoria" in value:
        return "Victoria", "victoria_explicita"
    if "eliminado" in value:
        return "Eliminado", "eliminado_explicito"
    if "abajo" in value:
        return "unknown", "abajo_ambiguo"
    if any(token in value for token in ("eliminacion", "eliminación")):
        return "Eliminacion", "eliminacion_o_variante"
    return "unknown", "sin_regla"


def canonical_class(value: object) -> str:
    normalized = normalize(value)
    if normalized == "eliminado":
        return "Eliminado"
    if normalized == "victoria":
        return "Victoria"
    if normalized in {"eliminacion", "eliminacion doble", "eliminacion triple", "eliminacion multiple", "abajo"}:
        return "Eliminacion"
    return "unknown"


def main() -> int:
    videos = pd.read_csv(DF_ROOT / "df_videos.csv", encoding="utf-8-sig")
    classification = pd.read_csv(DF_ROOT / "df_clasificacion.csv", encoding="utf-8-sig")
    videos["key"] = videos["video"].map(normalize)
    classification["key"] = classification["archivo"].map(normalize)
    merged = videos.merge(classification, on="key", how="left", suffixes=("_videos", "_clasificacion"))
    merged["filename_class"], merged["filename_rule"] = zip(*merged["video"].map(filename_rule))
    merged["classification_present"] = merged["clase_clasificacion"].notna()
    merged["class_match"] = merged["clase_videos"].map(canonical_class) == merged["clase_clasificacion"].fillna("").map(canonical_class)
    merged["filename_matches_df_videos"] = merged["filename_class"] == merged["clase_videos"]
    merged["filename_matches_df_videos"] = merged["filename_matches_df_videos"] | (
        (merged["filename_class"] == "unknown") & (merged["filename_rule"] == "abajo_ambiguo")
    )

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    DOC_ROOT.mkdir(parents=True, exist_ok=True)
    columns = [
        "video", "clase_videos", "etiqueta_videos", "clase_clasificacion",
        "clase_agrupada", "classification_present", "class_match", "filename_class",
        "filename_rule", "filename_matches_df_videos",
    ]
    merged[columns].to_csv(OUT_ROOT / "label_comparison.csv", index=False, encoding="utf-8-sig")

    summary = {
        "df_videos_rows": int(len(videos)),
        "df_clasificacion_rows": int(len(classification)),
        "matched_by_filename": int(merged["classification_present"].sum()),
        "missing_from_df_clasificacion": int((~merged["classification_present"]).sum()),
        "missing_classification_by_df_videos_class": merged.loc[~merged["classification_present"], "clase_videos"].value_counts().to_dict(),
        "class_distribution_df_videos": videos["clase"].value_counts().to_dict(),
        "class_distribution_filename_rules": merged["filename_class"].value_counts().to_dict(),
        "filename_rules": merged["filename_rule"].value_counts().to_dict(),
        "classification_pairs": {
            f"{left} | {right}": int(count)
            for (left, right), count in merged.loc[merged["classification_present"]]
            .groupby(["clase_videos", "clase_clasificacion"]).size().items()
        },
        "mismatched_rows": int((merged["classification_present"] & ~merged["class_match"]).sum()),
        "filename_mismatches_excluding_ambiguous": int((~merged["filename_matches_df_videos"] & (merged["filename_rule"] != "abajo_ambiguo")).sum()),
        "recommended_authority": "df_videos.csv para las tres clases iniciales",
        "reason": "Es la fuente completa de 751 videos y coincide con los DataFrames de modalidades; df_clasificacion.csv tiene 730 filas y no contiene los 21 videos Victoria.",
    }
    (OUT_ROOT / "label_validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    class_doc = """# Diccionario de clases y decisión de etiquetas

## Fuente recomendada

La fuente canónica inicial es `df_videos.csv` porque contiene los 751 videos,
las tres clases previstas y sus códigos `0`, `1` y `2`. Además, sus clases son
las que se repiten en `df_audio.csv`, `df_frames.csv` y los tres DataFrames de
recortes.

`df_clasificacion.csv` se conserva como fuente secundaria de auditoría. Tiene
730 filas, no incluye los 21 videos `Victoria` y conserva subclases o estados
que requieren interpretación (`Abajo`, `Eliminación doble`, `Eliminación
triple` y `Eliminación múltiple`).

## Clases canónicas

| Código | Nombre | Definición | Regla inicial |
|---:|---|---|---|
| 0 | `Eliminado` | El jugador termina eliminado o fuera de la partida | Coincidencia explícita con `Eliminado` y validación contra `df_videos.csv` |
| 1 | `Eliminacion` | El video está etiquetado con una o más eliminaciones, sin afirmar victoria | `Eliminación`, doble, triple o múltiple; `Abajo` queda marcado como ambiguo |
| 2 | `Victoria` | El video está etiquetado explícitamente como victoria | Coincidencia explícita con `Victoria` |

## Prioridad de reglas de nombre

1. `Victoria` explícita.
2. `Eliminado` explícito.
3. `Eliminación`, doble, triple o múltiple.
4. `Abajo` como `unknown` hasta revisión manual.
5. Sin coincidencia como `unknown`.

## Hallazgos

- `df_videos.csv`: 616 `Eliminacion`, 114 `Eliminado`, 21 `Victoria`.
- `df_clasificacion.csv`: 730 filas; las 21 filas ausentes corresponden a `Victoria`.
- Los 26 videos `Abajo` aparecen como `Eliminacion` en `df_videos.csv`, pero esa equivalencia debe documentarse como decisión del dataset y no como verdad semántica automática.
- No se autoriza entrenamiento hasta revisar los 26 casos `Abajo` y confirmar la semántica de los 21 videos `Victoria`.

## Objetivo binario del frontend

El adaptador conservará `winProbability` y `lossProbability` para compatibilidad:

- `lossProbability = P(Eliminado)`.
- `winProbability = P(Eliminacion) + P(Victoria)`.

Esta salida se denomina internamente resultado favorable/desfavorable y no debe
interpretarse como probabilidad real de ganar la partida. Los modelos internos
conservarán las tres clases.
"""
    (DOC_ROOT / "DICCIONARIO_CLASES.md").write_text(class_doc, encoding="utf-8")
    print(json.dumps({"summary": str(OUT_ROOT / "label_validation.json"), "comparison": str(OUT_ROOT / "label_comparison.csv")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
