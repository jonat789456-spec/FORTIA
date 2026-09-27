# Seguimiento del proyecto backend

## Cierre seguro y pausa — 2026-09-21 10:03:30

- Se creó `..\CONTINUAR_PROYECTO.md` como fuente principal para reanudar.
- Se revisaron reportes, modelos, manifiestos, contratos, scripts y pruebas.
- Backend: 22 pruebas aprobadas, con 2 advertencias externas deprecadas.
- Frontend: 6 pruebas aprobadas, build y lint aprobados.
- REST/WebSocket fueron verificados en una prueba viva previa.
- La prueba real con Fortnite, la lectura visual del HUD/inventario/mapa y la
  validación de transmisión permanecen pendientes.
- No existe entrenamiento activo ni proceso de captura activo.
- No hay listeners activos en los puertos 8000 o 5173 al cierre.
- `test` continúa sellado y no se evaluó.
- Motivo de la pausa: el usuario no puede ejecutar todavía la prueba manual.
- Siguiente actividad: seguir `PRUEBAS_MANUALES_FORTNITE.md`; no abrir `test`
  antes de cerrar las incidencias y congelar la configuración final.

## Verificación automática final — 2026-09-21

- Backend: `22 passed, 2 warnings`.
- Frontend: `6 passed`, build aprobada y lint aprobado.
- Reporte: `reports/integration/AUTOMATIC_CHECK_REPORT.md`.
- `test` continúa sellado; no se ejecutó la evaluación final.
- Fortnite continúa pendiente de prueba manual.
- `start_all.ps1` quedó preparado con procesos PowerShell separados; si el
  aislamiento local impide mantener Vite, usar los scripts separados.

## Registro del bloque: cierre automático y preparación de validación manual

- Estado: todas las tareas verificables automáticamente completadas; pendiente
  únicamente la prueba manual con Fortnite abierto.
- Se integraron recomendaciones explicables al pipeline y al WebSocket:
  `LOW_HEALTH`, `LOW_SHIELD`, `HIGH_ELIMINATION_RISK` y degradación por
  modalidad faltante.
- `EventHub` conserva hasta 200 eventos por sesión y `/summary` devuelve
  eventos y recomendaciones reales.
- Se implementó reconexión automática del WebSocket del frontend con backoff.
- Se agregaron scripts `scripts/start_backend.ps1`, `start_frontend.ps1`,
  `start_all.ps1` y `stop_all.ps1`.
- Se agregó explícitamente `websockets` a las dependencias del backend después
  de detectarse su ausencia durante la prueba viva.
- Prueba viva ejecutada: REST HTTP 200, frontend HTTP 200, WebSocket aceptado,
  eventos `session.status`, respuesta `system.pong`, pausa y resumen con cinco
  eventos.
- Backend: 22 pruebas aprobadas. Frontend: 6 pruebas aprobadas, build aprobada
  y lint aprobado sin advertencias.
- Documentos nuevos: `PRUEBAS_MANUALES_FORTNITE.md`,
  `PENDIENTES_PARA_FINALIZAR.md` y `docs/API_CONTRACT.md`.
- Evidencias: creada `evidencias_pruebas` con subcarpetas vacías; no se
  fabricaron capturas ni logs de Fortnite.
- `test` continúa sellado; no se ejecutó evaluación final.

## Registro del bloque: captura alternativa, extracción estructurada y fusión multimodal

- Estado: completado con validación pendiente de una ventana visible real.
- Captura: se añadió modo `alternative`, título exacto, coincidencia segura y
  filtro por proceso. El modo se etiqueta como `Modo de prueba de captura`.
- Se intentó validar con una instancia temporal de Notepad; el entorno no
  expuso un `MainWindowHandle` visible, por lo que no fue posible obtener una
  captura real. El proceso temporal se cerró y no se guardaron archivos.
- Fortnite continúa sin detectarse y queda pendiente la prueba manual con el
  juego abierto.
- Vida/escudo: `HealthShieldReader` devuelve valores entre 0 y 100 solo cuando
  detecta evidencia cromática suficiente; usa `null`, `low_confidence`,
  `stale` o `unavailable` sin convertir ausencia en cero.
- Inventario: `InventoryReader` devuelve cinco espacios, ocupación, rareza
  aproximada, confianza y recorte; no inventa nombres de objetos.
- Audio: continúa experimental con espectrogramas PNG; el modo real permanece
  `unavailable` sin audio crudo compatible.
- Fusión multimodal: se compararon promedio ponderado, regresión logística y
  Gradient Boosting usando exclusivamente `train` y `validation`.
- Modelo seleccionado: `multimodal-0.1.0`, regresión logística; F1 macro de
  validation `0.9920`, balanced accuracy `0.9962`, log loss `0.0585`.
- Ablación: retirar frames produjo F1 macro `0.9843`; retirar health `0.9211`;
  inventory `0.9839`; map `0.9839`; audio `0.9920`.
- Registro: `artifacts/registry.json` ahora incluye el artefacto multimodal,
  el orden de características y la máscara de disponibilidad.
- Pruebas: 19 backend aprobadas; frontend 6 aprobadas y compilación aprobada.
- Protección: `test` continúa sellado; no se ejecutó evaluación final.

## Registro de continuidad — conexión de baselines y runtime

- Estado: completado parcialmente; cargadores y pipeline base operativos.
- Los cinco baselines incluyen clases, forma de entrada, normalización,
  escalador, versión y métricas de `validation`.
- `artifacts/registry.json` quedó en versión 1.1 y `testUsedForSelection` sigue
  en `false`.
- El runtime usa un buffer de capacidad uno, descarte controlado de frames,
  captura configurable y secuencia ordenada de seis imágenes.
- Salud/escudo estructurado, inventario estructurado y audio crudo se publican
  como `unavailable` cuando no existe un extractor válido.
- Backend: 12 pruebas aprobadas. Frontend: 6 pruebas aprobadas, compilación
  aprobada y lint sin errores; permanecen cuatro advertencias preexistentes.
- Benchmark aislado en CPU registrado en
  `reports/performance/INFERENCE_BENCHMARK.md` y `.json`.
- No se detectó una ventana real de Fortnite durante esta ejecución; no existe
  audio crudo; health/inventory aún clasifican resultados y no leen HUD u
  objetos; la fusión sigue siendo promedio de probabilidades.
- No se ejecutó la evaluación final sobre `test`.
- Próximo bloque: validar captura con Fortnite o una ventana alternativa,
  completar estados `unavailable` en frontend y construir la fusión multimodal
  usando solo `train` y `validation`.

## Fase actual

Fase 20: evaluación de modelos independientes. Las fases de inspección,
auditoría, validación preliminar de etiquetas, reorganización, verificación del
frontend, EDA, split y baselines están completadas.

## Estado

En progreso.

## Actividades realizadas

- Inspección de proyecto y ausencia de `.git` en la raíz original.
- Auditoría de 51,096 archivos y 168,849,472,888 bytes.
- Detección de carpetas reales `FRAMES`, `AUDIO`, `INVENTARIO`, `MAPA`, `ORIGINAL` y `VIDA`.
- Validación de imágenes y videos: 0 corrupciones y 0 errores de `ffprobe`.
- Detección de 74 grupos de duplicados exactos.
- Confirmación de 751 IDs con video, frames, vida, inventario, mapa y espectrograma.
- Comparación entre `df_videos.csv` y `df_clasificacion.csv`.
- Creación del diccionario de clases.
- Movimiento del frontend a `frontend` y verificación posterior.
- Creación de la base FastAPI, ciclo de sesiones y WebSocket.
- EDA con tablas, resumen numérico y tres gráficas.
- Split estratificado por video con agrupación de duplicados y validación sin fuga.
- Baselines logísticos de frames, vida, inventario, mapa y audio.
- Fusión tardía por promedio de probabilidades en validation.
- Adaptador central de tres clases a `winProbability`/`lossProbability`.
- Integración inicial del modo API del frontend con REST y WebSocket.
- Detección explícita de captura no disponible y GPU no disponible.
- Instalación y prueba del módulo de captura Windows/audio; sin ventana Fortnite detectada en la sesión.
- Transformación Mel configurable con 32 kHz, 128 bandas, FFT 2048 y hop 512.

## Archivos principales creados

- `tools/audit_data.py`
- `tools/validate_labels.py`
- `reports/audit/audit_report.md`
- `reports/audit/audit_summary.json`
- `reports/audit/label_validation.json`
- `reports/audit/label_comparison.csv`
- `data/manifests/file_manifest.csv`
- `data/manifests/modality_matrix.csv`
- `data/manifests/duplicate_groups.csv`
- `docs/DICCIONARIO_CLASES.md`
- `app/main.py`
- `app/schemas.py`
- `app/sessions.py`
- `app/recommendations.py`
- `requirements/base.txt`
- `requirements/training.txt`
- `tools/run_eda.py`
- `tools/make_splits.py`
- `tools/train_baselines.py`
- `tools/evaluate_fusion.py`
- `artifacts/registry.json`
- `app/model_registry.py`
- `app/capture/windows.py`
- `app/prediction_adapter.py`
- `app/audio/capture.py`
- `app/inference/baseline.py`
- `config/recommendations.yaml`

## Pruebas ejecutadas

Frontend antes del movimiento:

- 6 pruebas aprobadas.
- Compilación Vite aprobada.
- Lint sin errores; permanecen 4 advertencias preexistentes de Fast Refresh.

Frontend después del movimiento:

- 6 pruebas aprobadas.
- Compilación Vite aprobada.
- Lint sin errores; permanecen las mismas 4 advertencias.

## Hallazgos y limitaciones

- `Victoria`: 21 videos.
- `df_clasificacion.csv`: 730 filas y ausencia de los 21 videos `Victoria`.
- `Abajo`: 26 videos; la fuente canónica los registra como `Eliminacion`, pero la semántica queda marcada como ambigua.
- `AUDIO` contiene 751 imágenes PNG de espectrograma; no se encontraron archivos de audio crudo.
- `ORIGINAL` contiene 28 PNG adicionales no representados como videos.
- El primer split por video reveló 34 grupos duplicados cruzados; se corrigió agrupando componentes conectados.
- El split final contiene 0 grupos duplicados cruzando conjuntos.
- La API carga y reporta los baselines registrados; la captura aún declara `unavailable` cuando Fortnite o sus dependencias no están disponibles.

## Pendientes

- Validación final de las 3 clases y decisión sobre los 26 `Abajo`.
- Pipelines de preprocesamiento completos y modelos mejorados.
- Integración de artefactos en inferencia.
- Captura de Fortnite y audio.
- Pipeline continuo con colas y backpressure.
- Evaluación final en `test` después de seleccionar modelos.
- Captura de Fortnite y audio.
- Integración real con frontend.

## Próximo paso

Integrar los baselines y el registro de artefactos en el servicio de inferencia, manteniendo `test` bloqueado.
