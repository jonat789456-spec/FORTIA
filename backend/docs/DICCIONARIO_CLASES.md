# Diccionario de clases y decisión de etiquetas

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
