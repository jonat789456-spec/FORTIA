# Pendientes para finalizar Fortnite IA

## Cierre actual

- Fecha de pausa: 2026-09-21.
- Fuente de continuidad: `CONTINUAR_PROYECTO.md`.
- El proyecto queda detenido de forma segura mientras se espera la prueba
  manual con Fortnite.
- `test` permanece sellado y no se ejecutó.
- No hay procesos del backend/frontend ni listeners en 8000/5173 al cierre.

## Completados

- Auditoría, EDA, split por video y exclusión de `Abajo`.
- Baselines, registro de modelos y benchmark.
- Modelo multimodal `multimodal-0.1.0` seleccionado con `train`/`validation`.
- API REST, WebSocket, pipeline continuo y frontend en modo demo/API.
- Estados `unavailable`, `stale` y `low_confidence`.
- Extracción estructurada conservadora de HUD e inventario.
- Scripts de inicio y detención.
- Pruebas automáticas backend/frontend, build y lint.

## Pendientes automáticos

Las suites, el build y el lint pasan. La ejecución del iniciador general
`start_all.ps1` debe confirmarse en una consola Windows interactiva, porque el
entorno automatizado restringió el proceso hijo de Vite. Como alternativa,
usar `start_backend.ps1` y `start_frontend.ps1` por separado.

No quedan bloqueos automáticos críticos conocidos. Las pruebas automáticas deben repetirse después de cualquier modificación realizada durante la prueba manual.

## Pendientes de prueba manual

| Descripción | Motivo | Responsable | Procedimiento | Criterio de aceptación | Prioridad |
|---|---|---|---|---|---|
| Capturar una ventana real de Fortnite | Fortnite no estuvo abierto en el entorno | Usuario + sistema | Seguir `PRUEBAS_MANUALES_FORTNITE.md` | Ventana detectada y captura real visible | Alta |
| Validar recortes contra HUD real | La lectura automática no puede verificarse sin juego | Usuario | Probar resoluciones y HUD visibles | Vida/escudo con confianza válida o estado correcto | Alta |
| Validar inventario real | No se observó una partida real | Usuario | Revisar cinco espacios y rarezas | Espacios correctos sin nombres inventados | Alta |
| Validar reconexión real | No hubo ventana disponible | Usuario + sistema | Minimizar, restaurar y cerrar Fortnite | Estados y recuperación correctos | Alta |
| Evaluar audio real | No existe audio crudo histórico | Usuario | Confirmar captura compatible o documentar `unavailable` | Nunca aparecen probabilidades ficticias | Media |
| Evaluación única sobre `test` | Debe congelarse primero el sistema completo | Usuario + sistema | Ejecutar únicamente tras aceptar manualmente el modelo | Reporte final separado y sin reajuste posterior | Alta |

## Pendientes por falta de datos

- Audio crudo sincronizado.
- Más videos reales de `Victoria`; solo existen 21.
- Regla verificable para los 26 casos `Abajo`.
- Etiquetas estructuradas de objetos de inventario.
- Etiquetas de vida, escudo, enemigos, posición y zona segura.

## Mejoras opcionales

- OCR o detector aprendido para HUD.
- Detector de objetos y munición.
- Calibración adicional con más datos.
- GPU y modelo temporal más expresivo.
- Métricas de recursos durante una partida prolongada.

## Bloqueos

- El sistema completo no puede declararse terminado sin Fortnite abierto.
- `test` debe permanecer sellado hasta cerrar ajustes y pruebas manuales.

## Recomendación del siguiente paso

Ejecutar la guía manual, completar la tabla de aceptación y entregar las evidencias. Después congelar configuración y realizar, si corresponde, la única evaluación final sobre `test`.
