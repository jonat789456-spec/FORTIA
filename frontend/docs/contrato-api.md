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
