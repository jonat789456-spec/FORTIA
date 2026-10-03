[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = 'C:\Users\jonat\Downloads\FORTNITE IA 2'
$Python = 'C:\Users\jonat\AppData\Local\Programs\Python\Python312\python.exe'
$Backend = Join-Path $ProjectRoot 'backend'
$Output = Join-Path $Backend 'artifacts\experimental_training_20261001'
$LogDir = Join-Path $Output 'logs'
$Log = Join-Path $LogDir 'training.log'
$Script = Join-Path $Backend 'tools\train_experimental_candidate.py'
$Split = Join-Path $Backend 'data\splits\video_split.csv'
$env:PYTHONPATH = $Backend

function Need([string]$Path, [string]$Name) { if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Falta ${Name}: ${Path}" } }
Need $Python 'Python'
Need $Script 'entrenador experimental'
Need $Split 'split histórico'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$start = Get-Date
"[$($start.ToString('o'))] CANDIDATO EXPERIMENTAL NO PROMOVIBLE" | Tee-Object -FilePath $Log
"[$($start.ToString('o'))] Comando: `"$Python`" `"$Script`" --output `"$Output`"" | Tee-Object -FilePath $Log -Append
"[$($start.ToString('o'))] PID PowerShell: $PID" | Tee-Object -FilePath $Log -Append
& $Python $Script --output $Output 2>&1 | Tee-Object -FilePath $Log -Append
$code = $LASTEXITCODE
$end = Get-Date
"[$($end.ToString('o'))] Código de salida: $code; duración: $($end-$start)" | Tee-Object -FilePath $Log -Append
"[$($end.ToString('o'))] Log: $Log" | Tee-Object -FilePath $Log -Append
if ($code -ne 0) { throw "El entrenamiento experimental terminó con código $code" }
Write-Host 'ENTRENAMIENTO EXPERIMENTAL COMPLETADO' -ForegroundColor Green
