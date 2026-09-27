# Arquitectura frontend

## Decisiones

- React, TypeScript y Vite para una SPA mantenible.
- CSS Modules conceptualmente mediante estilos organizados en un archivo global de tokens y componentes.
- Zustand para sesión, conexión y datos de tiempo real.
- TanStack Query disponible para consultas REST futuras.
- Zod para validar respuestas externas.
- Lucide React para iconografía accesible.
- REST para comandos y consultas; WebSocket para eventos frecuentes.

## Principios

1. El visor de partida conserva la prioridad visual.
2. Las modalidades independientes no bloquean el dashboard completo.
3. Las probabilidades binarias nunca se mezclan con las tres clases principales.
4. La aplicación consume exclusivamente el flujo API real.
5. Eventos antiguos no reemplazan datos recientes.

## Componentes

App, MainPredictionCard, StreamViewer, HealthPanel, InventoryPanel, BinaryModelPanel, SequencePanel, AlertsPanel, RecommendationsPanel, Modal y componentes de estado compartidos.

## Estados visuales

Todos los módulos contemplan idle, waiting, processing, ready, stale, unavailable, error, offline y reconnecting, aunque la demo prioriza los estados más relevantes para una presentación continua.
