# FORTIA — Frontend de análisis de IA en tiempo real

Dashboard frontend para visualizar transmisión, señales de juego y predicciones independientes y multimodales. Funciona sin backend mediante el modo demostración y está preparado para REST y WebSocket.

## Instalación

Requisitos: Node.js 20 o superior y npm.

    npm install
    npm run dev

En PowerShell con ejecución de scripts restringida se puede utilizar npm.cmd.

## Scripts

- npm run dev: servidor de desarrollo.
- npm run build: TypeScript y compilación de producción.
- npm run test: pruebas automatizadas.
- npm run lint: revisión ESLint.

## Modos de datos

La aplicación inicia en Modo demostración. Para API real, copia .env.example a .env, configura VITE_API_BASE_URL y VITE_WS_BASE_URL, y cambia VITE_DATA_SOURCE=api.

## Documentación

- docs/PROYECTO_FRONTEND.md: avance por fases.
- docs/arquitectura-frontend.md: decisiones técnicas y visuales.
- docs/contrato-api.md: endpoints y eventos.
- docs/flujo-demostracion.md: recorrido de cinco minutos.
