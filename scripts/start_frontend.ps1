$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
Set-Location $frontendRoot

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { Write-Host 'ERROR: npm no está disponible en PATH.' -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar'; exit 1 }
if (-not (Test-Path (Join-Path $frontendRoot 'node_modules'))) { Write-Host 'Instalando dependencias del frontend...' -ForegroundColor Yellow; npm.cmd install }
$portInUse = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) { Write-Host 'El frontend ya parece estar escuchando en http://localhost:5173' -ForegroundColor Yellow; Read-Host 'Presiona Enter para cerrar'; exit 0 }
Write-Host 'Frontend: http://localhost:5173' -ForegroundColor Cyan
npm.cmd run dev -- --host 127.0.0.1
if ($LASTEXITCODE -ne 0) { Write-Host 'El frontend terminó con error.' -ForegroundColor Red; Read-Host 'Presiona Enter para cerrar' }
