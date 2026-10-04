# Despliegue público de FORTIA

## Arquitectura

El frontend es una aplicación Vite/React y se publica como proyecto independiente en Vercel usando `frontend` como directorio raíz. El backend es FastAPI y debe ejecutarse como servicio ASGI persistente con `CAPTURE_MODE=web`; no debe ejecutarse en Vercel Functions porque mantiene sesiones, tareas de inferencia y WebSockets.

En modo público, el navegador solicita `getDisplayMedia` después de pulsar **Iniciar análisis**. El usuario elige la ventana o pantalla de Fortnite. El navegador limita la captura a 5 FPS, reduce el ancho máximo a 1280 px y envía JPEG pequeños al endpoint `POST /api/v1/sessions/{id}/frames`. El backend conserva solo el último frame pendiente y descarta frames atrasados.

La captura nativa Windows/WASAPI queda reservada para desarrollo local. El modo web no captura audio del servidor; por eso Audio aparece como no disponible salvo que se implemente un canal de audio web consentido posteriormente.

## Variables

Frontend (`frontend/.env` o Vercel):

```text
VITE_API_BASE_URL=https://TU_BACKEND/api/v1
VITE_WS_BASE_URL=wss://TU_BACKEND/api/v1/ws
```

Backend:

```text
CAPTURE_MODE=web
HOST=0.0.0.0
PORT=8000
FRONTEND_ORIGIN=https://TU_PROYECTO.vercel.app
FRONTEND_ORIGINS=https://TU_PROYECTO.vercel.app
WEB_FRAME_MAX_WIDTH=1280
WEB_FRAME_MAX_BYTES=250000
```

No se deben subir archivos `.env` reales ni credenciales.

## Desarrollo local

```powershell
cd "C:\ruta\a\FORTIA"
Copy-Item frontend\.env.example frontend\.env
cd frontend
npm.cmd install
npm.cmd run dev
```

Para ejecutar la API local con captura nativa, usa los scripts existentes. Para probar el flujo web contra una API local, configura `CAPTURE_MODE=web` y `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`.

## Vercel

1. Importa el repositorio `FORTIA`.
2. Configura `frontend` como **Root Directory**.
3. Usa framework **Vite**, `npm run build` y salida `dist`.
4. Configura `VITE_API_BASE_URL` y `VITE_WS_BASE_URL` con URLs HTTPS/WSS reales.
5. Genera primero un Preview Deployment.
6. Verifica `/healthz`, CORS, WebSocket y un frame real antes de producción.

El backend no debe apuntar a `127.0.0.1` en producción. Necesita un servicio que soporte FastAPI, tareas persistentes, WebSockets y los artefactos incluidos. El `backend/Dockerfile` prepara el modo web y solo copia los artefactos activos.

## Uso y privacidad

1. Abre Fortnite en modo ventana o pantalla completa en ventana.
2. Abre FORTIA y pulsa **Iniciar análisis**.
3. Acepta el permiso del navegador y selecciona Fortnite.
4. Mantén la fuente compartida durante el análisis.
5. Pulsa **Reiniciar** o detén la fuente desde el navegador para terminar.

FORTIA no guarda video ni audio por defecto. Procesa temporalmente frames JPEG reducidos; no envía 60 FPS y descarta frames antiguos si el backend se retrasa. Las predicciones son una ayuda y no garantizan el resultado de una partida.

## Estado verificado (2026-10-04)

- Frontend Preview publico: https://fortia-nu.vercel.app
- Backend Preview HTTPS: https://fortia-api-nu.vercel.app
- Health check: https://fortia-api-nu.vercel.app/healthz
- `CAPTURE_MODE=web`, CORS restringido al frontend y los siete modelos activos cargan correctamente.
- Se verifico CORS, creacion de sesion y aceptacion de un frame JPEG comprimido.
- Estado: `FRONTEND PUBLICO, BACKEND LIMITADO POR VERCEL`.

Vercel Functions no conserva de forma fiable el estado de las sesiones, tareas de inferencia y colas entre solicitudes. En la prueba real, el primer frame fue aceptado, pero una solicitud posterior recibio `Sesion no encontrada`; por ello no se publica produccion ni se declara una inferencia completa. El backend necesita un servicio ASGI persistente con FastAPI, WebSockets, CPU/memoria para los modelos y proceso de larga duracion.

## Limitaciones conocidas

- La captura web requiere HTTPS, excepto en `localhost`.
- El audio WASAPI es local y no está disponible en un backend Linux público.
- El backend público debe tener CORS limitado al dominio de Vercel, límites de carga y rate limiting del proveedor.
- No se debe declarar la aplicación como funcional públicamente hasta verificar desde un navegador externo una inferencia completa.
