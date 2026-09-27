$ErrorActionPreference = 'SilentlyContinue'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot '.runtime'
foreach ($name in @('backend.pid', 'frontend.pid')) {
  $pidFile = Join-Path $runtimeRoot $name
  if (Test-Path $pidFile) {
    $processId = [int](Get-Content $pidFile | Select-Object -First 1)
    $descendants = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId" | Select-Object -ExpandProperty ProcessId)
    foreach ($childId in $descendants) {
      Stop-Process -Id ([int]$childId) -Force -ErrorAction SilentlyContinue
    }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $processId -Force }
    Remove-Item -LiteralPath $pidFile -Force
  }
}
Write-Host 'Procesos iniciados por start_all.ps1 detenidos. Si se inició un servicio manualmente, ciérralo desde su consola.' -ForegroundColor Cyan
