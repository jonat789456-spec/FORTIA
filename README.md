# Fortnite Vision AI (FORTIA)

FORTIA es una aplicación local para analizar partidas de Fortnite mediante un backend Python/FastAPI y un frontend React/Vite. El frontend funciona exclusivamente contra la API real; no incluye fallback de datos simulados para el usuario final.

## Estructura

- `backend/`: API REST, WebSocket, captura, inferencia, lectores del HUD y pruebas.
- `frontend/`: panel React/Vite y cliente REST/WebSocket.
- `scripts/`: comandos PowerShell para iniciar y detener la aplicación.
- `backend/config/`: configuración de detectores y umbrales.
- `backend/data/`: manifiestos y metadatos ligeros; los datos multimedia originales no se versionan.

## Requisitos

- Windows 10/11.
- Python 3.11 o posterior.
- Node.js 18 o posterior y npm.
- Fortnite instalado si se desea utilizar la captura de ventana.

## Instalación

Desde la raíz del proyecto:

```powershell
cd "C:\ruta\a\FORTIA"
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements\base.txt
cd frontend
npm.cmd install
cd ..
```

Copia los archivos de ejemplo si necesitas personalizar la configuración:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

Los archivos `.env` reales están ignorados por Git.

## Ubicación de los datos

Por defecto, el backend usa rutas relativas para datos locales fuera del despliegue público. Configura `DATA_VIDEOS_ROOT`, `DATA_DF_ROOT` y `AUDIO_RAW_ROOT` solo en tu entorno local.

Las rutas configurables se encuentran en `backend/.env.example`. Las carpetas `VIDEOS`, `VIDA`, `ORIGINAL`, `DF`, frames, audios y videos no se eliminan del equipo y no se publican en Git.

## Ejecución

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_all.ps1
```

Direcciones locales:

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`

Para detener los procesos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_all.ps1
```

## Pruebas y calidad

```powershell
cd backend
python -m pytest -q
cd ..\frontend
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run build
```

## Despliegue público

La arquitectura web pública y las instrucciones para Vercel, el backend FastAPI, la captura autorizada mediante navegador y las limitaciones de privacidad están documentadas en [DEPLOYMENT_PUBLICO.md](DEPLOYMENT_PUBLICO.md). El backend de producción debe usar `CAPTURE_MODE=web`; no se debe publicar una configuración que intente capturar `127.0.0.1` o una ventana Windows del servidor.

## Seguridad y archivos excluidos

Git ignora credenciales, `.env`, entornos virtuales, cachés, dependencias instaladas, builds, logs, datos multimedia originales, evidencias generadas y modelos pesados. Estos archivos permanecen intactos en el equipo local.
