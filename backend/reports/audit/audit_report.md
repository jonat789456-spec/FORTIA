# Reporte de auditoría de datos

Generado: `2026-09-21T11:52:46.273396+00:00`

## Alcance

Auditoría de solo lectura. Las fuentes originales no fueron modificadas.

- Videos root: `F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS`
- DataFrames root: `F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF`
- Archivos inspeccionados: **51096**
- Bytes inspeccionados: **168,849,472,888**

## Carpetas detectadas

| Modalidad | Carpeta real | IDs únicos |
|---|---|---:|
| frames | `FRAMES` | 751 |
| audio | `AUDIO` | 751 |
| inventory | `INVENTARIO` | 751 |
| map | `MAPA` | 751 |
| original | `ORIGINAL` | 751 |
| health | `VIDA` | 751 |

## Clases por DataFrame

```json
{
  "df_audio.csv": {
    "Eliminacion": 616,
    "Eliminado": 114,
    "Victoria": 21
  },
  "df_clasificacion.csv": {
    "Eliminación": 542,
    "Eliminado": 114,
    "Eliminación doble": 43,
    "Abajo": 26,
    "Eliminación triple": 3,
    "Eliminación múltiple": 2
  },
  "df_frames.csv": {
    "Eliminacion": 3696,
    "Eliminado": 684,
    "Victoria": 126
  },
  "df_recortes_inventario.csv": {
    "Eliminacion": 12320,
    "Eliminado": 2280,
    "Victoria": 420
  },
  "df_recortes_mapa.csv": {
    "Eliminacion": 12320,
    "Eliminado": 2280,
    "Victoria": 420
  },
  "df_recortes_vida.csv": {
    "Eliminacion": 12320,
    "Eliminado": 2280,
    "Victoria": 420
  },
  "df_videos.csv": {
    "Eliminacion": 616,
    "Eliminado": 114,
    "Victoria": 21
  }
}
```

## Reglas de nombres

```json
{
  "counts": {
    "Eliminacion": 590,
    "Victoria": 21,
    "unknown": 26,
    "Eliminado": 114
  },
  "rules": {
    "elimination_variant": 590,
    "explicit_victory": 21,
    "ambiguous_abajo": 26,
    "explicit_eliminated": 114
  }
}
```

## Calidad preliminar

- Imágenes corruptas: **0**
- Videos con error de ffprobe: **0**
- Grupos de duplicados exactos: **74**
- PNG dentro de ORIGINAL: **28**

## Archivos generados

- `backend/reports/audit/audit_summary.json`
- `backend/reports/audit/dataframe_summary.json`
- `backend/data/manifests/file_manifest.csv`
- `backend/data/manifests/modality_matrix.csv`
- `backend/data/manifests/duplicate_groups.csv`

## Dictamen

Las etiquetas y la suficiencia de las clases deben validarse antes del entrenamiento. Este reporte no autoriza por sí mismo el entrenamiento y debe complementarse con revisión de inconsistencias entre DataFrames.
