# Contrato de integración API v1

## Campos comunes

Cada evento puede incluir sessionId, predictionId, timestamp, source, status, modelVersion, data y error. El frontend ignora eventos de otra sesión o con timestamp anterior al dato aceptado.

## REST

| Método | Ruta | Uso |
|---|---|---|
| GET | /system/status | Salud y capacidades |
| POST | /sessions | Crear sesión |
| POST | /sessions/{id}/start | Iniciar análisis |
| POST | /sessions/{id}/pause | Pausar |
| POST | /sessions/{id}/resume | Reanudar |
| POST | /sessions/{id}/finish | Finalizar |
| GET | /sessions/{id} | Estado de sesión |
| GET | /sessions/{id}/summary | Resumen |

## WebSocket

La conexión esperada es /ws/sessions/{sessionId}. Eventos: session.status, stream.updated, health_shield.updated, inventory.updated, audio_prediction.updated, frame_sequence.updated, map.updated, main_prediction.updated, alert.created, recommendation.created y model.status.

`stream.updated` transporta el JPEG como mensaje binario con una cabecera JSON terminada en salto de línea; el frontend crea y revoca un `ObjectURL` por frame. En fallback de pruebas se conserva Base64. El evento se produce desde una ranura de último frame independiente de las inferencias e incluye `captureFps`, `streamFps`, `captureMs`, `resizeMs`, `encodeMs`, `imageBytes`, `capturedAt`, `encodedAt`, `latencyMs`, `sendMs`, `resolutionSource` y `framesDropped`. El frontend actualiza el elemento visual mediante `requestAnimationFrame` y limita las actualizaciones del resto de la interfaz.

`inventory.updated` contiene una sola imagen JPEG horizontal en `image` para la
presentación, mientras `items` conserva los cinco resultados estructurados del
lector interno. `imageIsStale` e `imageAgeMs` identifican una imagen válida
retenida temporalmente durante una lectura no confiable.

## Predicciones

El evento `health_shield.updated` diferencia `current` y `max` para vida,
escudo y overshield. El panel, las alertas y la voz consumen el valor
`current`; `last_stable` nunca se etiqueta como `Actual`.

Las modalidades independientes devuelven winProbability y lossProbability. El modelo principal devuelve eliminatedProbability, eliminationProbability y victoryProbability. La suma esperada del modelo principal es aproximadamente 1.

## Configuración

- VITE_API_BASE_URL: base REST.
- VITE_WS_BASE_URL: base WebSocket.
- VITE_API_BASE_URL: URL base configurable del cliente REST.
- VITE_WS_BASE_URL: URL base configurable del cliente WebSocket.

## Integración con Python

El backend puede devolver JSON con los mismos campos sin depender de la implementación interna de los modelos. La capa services.ts es el único punto que conoce las URLs y la conexión WebSocket.
