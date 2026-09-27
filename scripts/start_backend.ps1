$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
Set-Location $backendRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Host 'ERROR: Python no está disponible en PATH.' -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar'; exit 1 }
python -c "import fastapi, uvicorn, joblib" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host 'ERROR: faltan dependencias del backend. Instala requirements/base.txt y requirements/training.txt.' -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar'; exit 1 }
$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) { Write-Host 'El backend ya parece estar escuchando en http://127.0.0.1:8000' -ForegroundColor Yellow; Read-Host 'Presiona Enter para cerrar'; exit 0 }
Write-Host 'Backend: http://127.0.0.1:8000' -ForegroundColor Cyan
Write-Host 'API: http://127.0.0.1:8000/docs' -ForegroundColor Cyan
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
if ($LASTEXITCODE -ne 0) { Write-Host 'El backend terminó con error.' -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar' }
