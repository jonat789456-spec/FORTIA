# Registro del proyecto frontend

## Estado actual

- Fase actual: Fase 10 — Preparación para demostración.
- Estado: Completada la implementación inicial y verificada. Rediseño visual completado.
- Fecha: 2026-09-20.
- Ruta local: la carpeta raíz del proyecto.
- Repositorio Git: No existía al comenzar.

## Actividades terminadas

- Inspección de carpeta y elementos ocultos.
- Confirmación de carpeta limpia y sin archivos previos que conservar.
- Creación de Vite, React y TypeScript.
- Sistema visual oscuro original para FORTIA.
- Dashboard con KPIs, visor central, modalidades, alertas y recomendaciones.
- Conexión API con actualizaciones en tiempo real.
- Adaptadores REST, WebSocket y validación Zod.
- Estados de conexión, procesamiento, error y reconexión preparados.
- Pruebas automatizadas de contratos y datos simulados.
- Documentación de integración y recorrido de demo.
- Inspección de estilos globales y confirmación de CSS tradicional con variables en src/styles.css.
- Actualización de la paleta a fondos #020617/#050B18, superficies escalonadas y acentos cian, azul eléctrico, morado, magenta, verde, dorado, naranja y rojo.
- Aplicación de profundidad visual, bordes semánticos, sombras, gradientes y estados de interacción.
- Diferenciación visual de rarezas del inventario y clases de predicción.

## Actividades pendientes

- Conectar el backend Python real.
- Sustituir placeholders históricos por imágenes reales autorizadas.
- Confirmar contratos definitivos y nombres de eventos con backend.
- Ejecutar prueba visual final con OBS y resolución objetivo.

## Archivos importantes

- src/App.tsx: shell principal del dashboard.
- src/components.tsx: componentes visuales.
- src/styles.css: sistema visual y responsive.
- src/store.ts: estado global Zustand.
- src/demo.ts: snapshot de datos simulados.
- src/realtime.ts: reloj de actualización de demo.
- src/services.ts: REST y WebSocket.
- src/schemas.ts: validación de respuestas.
- src/types.ts: contratos TypeScript.
- docs/contrato-api.md: integración v1.

## Verificaciones

- npm run build: correcto.
- npm run test: 6 pruebas correctas en 3 archivos después del rediseño.
- npm run build: compilación de producción correcta.
- npm run lint: 0 errores; 4 advertencias previas y no bloqueantes de Fast Refresh.
- npm run lint: 0 errores; 4 advertencias no bloqueantes de Fast Refresh.

## Problemas encontrados

- npm.ps1 está bloqueado por la política de PowerShell; se utiliza npm.cmd.
- Vite/esbuild requiere permisos elevados en este entorno para compilar.
- La carpeta no contenía una imagen local de referencia; el visual se basó en la especificación aprobada.

## Próximo paso recomendado

Configurar las variables de entorno y conectar progresivamente los eventos reales del backend, comenzando por el estado de sesión y la transmisión.
