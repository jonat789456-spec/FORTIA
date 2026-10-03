# Contrato API y WebSocket — versión 1.1

## REST

- `GET /api/v1/system/status`
- `GET /api/v1/models`
- `GET /api/v1/config`
- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{session_id}/start`
- `POST /api/v1/sessions/{session_id}/pause`
- `POST /api/v1/sessions/{session_id}/resume`
- `POST /api/v1/sessions/{session_id}/finish`
- `POST /api/v1/sessions/{session_id}/reset`
- `GET /api/v1/sessions/{session_id}`

## WebSocket

`/api/v1/ws/sessions/{session_id}`

Cada evento incluye `contractVersion`, `sessionId`, `predictionId`, `timestamp`,
`source`, `status` y un objeto `data`.

Eventos principales:

- `capture.status`: estado, modo (`fortnite` o `alternative`), frames capturados y descartados.
- `stream.updated`: la cabecera JSON describe el frame y el JPEG se transporta
  como binario separado por un salto de línea; el fallback Base64 solo se usa
  cuando el pipeline no recibe un publicador binario. Incluye resolución, FPS,
  `captureFps`, `streamFps`, tiempos de captura/redimensionamiento/codificación,
  tamaño, latencia, envío y frames descartados.
- `health_shield.updated`: `healthValue`, `shieldValue`, confianza de lectura,
  El evento rápido incluye `capturedAt`, `processedAt`, `processingMs` y
  `healthFramesDropped` para medir frescura y frames descartados.
  región, vigencia y estado. Los valores pueden ser `null`.
- `inventory.updated`: una imagen JPEG horizontal de la región completa en
  `inventoryImage` (también disponible como alias `image`), más los cinco espacios estructurados en `items` (ocupación, rareza,
  categoría opcional, cantidad y confianza). Los recortes individuales no se
  transmiten; el backend conserva el análisis por slot. `imageIsStale` e
  `imageAgeMs` identifican temporalmente la última imagen válida.
- `audio_prediction.updated`: captura `WASAPI Loopback` del dispositivo de salida (nunca micrófono), con `device`, `deviceId`, `nativeSampleRate`, `channels`, `bufferReady`, `modelLoaded`, `quality`, `level`, `rms`, `peak`, `waveform` y, cuando hay señal válida, las probabilidades del modelo crudo. `silence` significa captura activa sin señal; `device_unavailable` significa error técnico con reintentos.
- `map.updated`: recorte y predicción del mapa.
- `frame_sequence.updated`: seis frames ordenados y predicción temporal.
- `main_prediction.updated`: probabilidades de las tres clases, confianza,
  modalidades participantes y ausentes, latencia y versión.

## Reglas de validez

El evento `health_shield.updated` mantiene los alias `healthValue` y
`shieldValue` por compatibilidad, pero los consumidores nuevos deben usar:

```json
{
  "health": {"current": 100, "max": 100},
  "shield": {"current": 47, "max": 100},
  "overshield": {"current": null, "max": null, "status": "not_applicable"}
}
```

`current` y `max` son campos distintos. `estimated`, `last_stable` y `stale`
incluyen antigüedad; solo `current` representa evidencia del frame actual.

- Las probabilidades solo aparecen con `status=ready` y suman aproximadamente 1.
- `unavailable`, `low_confidence` y `stale` no se representan como cero.
- La secuencia temporal es obligatoria para la predicción principal.
- El modo alternativo siempre se etiqueta como `Modo de prueba de captura`.
- Cuando está disponible, `audio_prediction.updated` contiene `source: wasapi_loopback`, `classProbabilities` multiclase, `predictedClass`, `confidence`, `quality`, `level`, `silence`, `latencyMs`, `capturedAt` y `modelVersion`.
- En silencio se publica `status: silence` sin probabilidades; la ausencia no se convierte en evidencia negativa para la fusión multimodal.
- `test` no forma parte de ningún contrato de selección o calibración actual.
