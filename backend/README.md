# Backend de Fortnite IA

Backend local para captura, preprocesamiento, inferencia multimodal y comunicación con el frontend.

## Estado actual

- Auditoría reproducible de datos completada.
- Etiquetas comparadas y documentadas.
- Frontend reorganizado y verificado en `../frontend`.
- API REST, WebSocket y pipeline continuo disponibles.
- Cinco baselines y el modelo multimodal `multimodal-0.1.0` registrados.
- Captura de Fortnite configurable; la captura alternativa se etiqueta explícitamente.

## Continuidad del estado

El split por video está corregido con exclusión de casos ambiguos y sin fuga.
Hay cinco baselines entrenados únicamente con `train` y `validation`, con
registro central y cargadores de inferencia. La API REST, WebSocket y el
pipeline continuo base están disponibles. La captura Windows es configurable y
degrada a `unavailable` si Fortnite no está abierto. El audio histórico existe
solo como espectrograma PNG; la captura de audio crudo aún no está conectada.
La evaluación final sobre `test` permanece pendiente y sellada.

Comandos del bloque actual:

```powershell
python tools/build_registry.py
python -m tools.benchmark_inference
pytest -q
```

## Ejecutar la API

## Estado del bloque multimodal

La fusión `multimodal-0.1.0` está registrada y se carga una sola vez. Fue
seleccionada con `train`/`validation`; `test` continúa sellado. La captura
admite modo Fortnite o modo alternativo configurable por `CAPTURE_MODE`,
`CAPTURE_WINDOW_TITLE`, `CAPTURE_WINDOW_TITLE_EXACT` y
`CAPTURE_PROCESS_NAME`. El modo alternativo se publica como `Modo de prueba de
captura`.

Vida/escudo e inventario tienen extracción estructurada conservadora. Los
valores no detectables se publican como `null` con estado `low_confidence`,
`stale` o `unavailable`. El audio real continúa no disponible porque los datos
históricos son espectrogramas PNG y no audio crudo.

Desde `backend`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

La API permanece local y expone:

- `GET /api/v1/system/status`
- `POST /api/v1/sessions`
- Ciclo de vida bajo `/api/v1/sessions/{session_id}`
- WebSocket `/api/v1/ws/sessions/{session_id}`

## Auditoría

```powershell
python tools/audit_data.py
python tools/validate_labels.py
```

Las fuentes en la unidad `F:` se leen sin modificación. Los reportes derivados están en `reports/audit` y los manifiestos en `data/manifests`.
