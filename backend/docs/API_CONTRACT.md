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
- `stream.updated`: imagen JPEG, resolución, FPS y `captureMode`.
- `health_shield.updated`: `healthValue`, `shieldValue`, confianza de lectura,
  región, vigencia y estado. Los valores pueden ser `null`.
- `inventory.updated`: cinco espacios estructurados, ocupación, rareza,
  categoría opcional, cantidad opcional, confianza y recorte.
- `audio_prediction.updated`: puede ser `unavailable` si no hay audio crudo.
- `map.updated`: recorte y predicción del mapa.
- `frame_sequence.updated`: seis frames ordenados y predicción temporal.
- `main_prediction.updated`: probabilidades de las tres clases, confianza,
  modalidades participantes y ausentes, latencia y versión.

## Reglas de validez

- Las probabilidades solo aparecen con `status=ready` y suman aproximadamente 1.
- `unavailable`, `low_confidence` y `stale` no se representan como cero.
- La secuencia temporal es obligatoria para la predicción principal.
- El modo alternativo siempre se etiqueta como `Modo de prueba de captura`.
- `test` no forma parte de ningún contrato de selección o calibración actual.
