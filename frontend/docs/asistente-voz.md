# Asistente de voz de FORTIA

## Arquitectura

El asistente está implementado en `src/voice.tsx` y usa la API nativa
`speechSynthesis` del navegador. No agrega dependencias, no envía capturas ni
predicciones a servicios externos y no modifica el backend. `VoiceAssistant`
se suscribe al store de Zustand, por lo que consume tanto el modo API como el
datos reales del backend a través del mismo estado que renderiza el dashboard.

El motor mantiene una única cola de voz. Las alertas críticas pueden desplazar
mensajes informativos pendientes; los mensajes vencidos, duplicados u obsoletos
se descartan antes de reproducirse.

## Eventos consumidos

Se procesan los estados derivados de estos eventos WebSocket existentes:

- `session.status`, `stream.updated` y `capture.status`: inicio, captura y conexión.
- `main_prediction.updated`: clase principal, riesgo de eliminación y cambios de probabilidad.
- `health_shield.updated`: vida y escudo.
- `inventory.updated`: recomendaciones del inventario cuando el backend las proporciona.
- `audio_prediction.updated` y `map.updated`: modalidades no disponibles.
- `recommendation.updated`: recomendaciones reales del backend.
- Alertas agregadas al store: prioridad crítica, alta, media o informativa.

Las clases se traducen únicamente desde los valores del contrato actual:
`eliminated` → `Eliminado`, `elimination` → `Eliminación` y `victory` →
`Victoria`.

## Umbrales y estabilidad

- Riesgo bajo: menor de 40 %.
- Riesgo medio: 40–59 %.
- Riesgo alto: 60–79 %.
- Riesgo crítico: 80 % o más.
- Los cambios de probabilidad relevantes requieren 10 puntos porcentuales.
- Un cambio de clase debe mantenerse durante tres actualizaciones consecutivas.
- El margen inicial de estabilidad entre clases es de 8 puntos porcentuales.
- Enfriamiento normal: 8 segundos.
- Enfriamiento crítico: 4 segundos.
- Dedupe por mensaje: 30 segundos.
- Límite normal: 6 mensajes por minuto.

Estos valores están centralizados en `DEFAULT_SETTINGS` y se guardan en
`localStorage` bajo `fortia.voice.settings`.

## Controles y privacidad

El botón de altavoz del dock abre el panel de configuración. El usuario puede
activar la voz explícitamente, seleccionar una voz española disponible,
ajustar volumen, velocidad, tono y frecuencia, probarla o detenerla. La voz
queda desactivada inicialmente para cumplir las restricciones de interacción
de los navegadores.

El asistente no almacena conversaciones, no incorpora reconocimiento de voz y
no realiza llamadas externas. Si el navegador no ofrece `speechSynthesis`, el
panel muestra la indisponibilidad sin afectar el resto del dashboard.

## Extensión futura

Para agregar otra frase, añádela en el método que procesa la señal real
correspondiente y asígnale una prioridad y una clave de deduplicación. Para
conectar otro motor TTS, se puede reemplazar únicamente `processQueue`,
manteniendo la cola, los límites y la capa de generación de lenguaje.
