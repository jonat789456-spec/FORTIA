$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python no está disponible en PATH.' }
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) { throw 'Node.js no está disponible en PATH.' }
if (-not (Test-Path (Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'))) {
  throw 'Faltan dependencias del frontend. Ejecuta scripts\start_frontend.ps1 o npm.cmd install dentro de frontend.'
}

function Test-Port($port) { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
if (-not (Test-Port 8000)) {
  $backendDir = Join-Path $projectRoot 'backend'
  $backendLog = Join-Path $runtimeRoot 'backend.stdout.log'
  $backendCommand = "Set-Location -LiteralPath '$backendDir'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info *>> '$backendLog'"
  $backend = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-NoExit', '-Command', $backendCommand) -WindowStyle Minimized -PassThru
  Set-Content -Path (Join-Path $runtimeRoot 'backend.pid') -Value $backend.Id
} else { Write-Host 'Backend ya activo en el puerto 8000.' -ForegroundColor Yellow }
Start-Sleep -Seconds 2
if (-not (Test-Port 5173)) {
  $frontendDir = Join-Path $projectRoot 'frontend'
  $nodePath = (Get-Command node.exe).Source
  $vitePath = Join-Path $frontendDir 'node_modules/vite/bin/vite.js'
  $frontendLog = Join-Path $runtimeRoot 'frontend.stdout.log'
  $frontendCommand = "Set-Location -LiteralPath '$frontendDir'; & '$nodePath' '$vitePath' --host 127.0.0.1 *>> '$frontendLog'"
  $frontend = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-NoExit', '-Command', $frontendCommand) -WindowStyle Minimized -PassThru
  Set-Content -Path (Join-Path $runtimeRoot 'frontend.pid') -Value $frontend.Id
} else { Write-Host 'Frontend ya activo en el puerto 5173.' -ForegroundColor Yellow }
Start-Sleep -Seconds 3
Write-Host 'Abre manualmente http://127.0.0.1:5173 si el navegador no se inicia automaticamente.' -ForegroundColor Yellow
Write-Host 'Backend: http://127.0.0.1:8000/docs' -ForegroundColor Cyan
Write-Host 'Frontend: http://127.0.0.1:5173' -ForegroundColor Cyan
Write-Host 'Para detener: scripts\stop_all.ps1' -ForegroundColor Cyan
