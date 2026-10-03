[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = 'C:\Users\jonat\Downloads\FORTNITE IA 2'
$BackendRoot = Join-Path $ProjectRoot 'backend'
$PipelineRoot = Join-Path $BackendRoot 'temporal_labeling'
$Python = 'C:\Users\jonat\AppData\Local\Programs\Python\Python312\python.exe'
$RunPipeline = Join-Path $PipelineRoot 'run_pipeline.py'
$Detector = Join-Path $PipelineRoot 'detector.py'
$Readme = Join-Path $PipelineRoot 'README.md'
$VideosRoot = 'F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS\ORIGINAL'
$VideoCsv = 'F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\DF\df_videos.csv'
$OutputRoot = Join-Path $BackendRoot 'data\automatic_temporal_annotations\full_run_v0.4.0'
$ReleaseRoot = Join-Path $BackendRoot 'data\automatic_temporal_annotations\release_v0.4.0'
$CachePath = Join-Path $ReleaseRoot 'full_ocr_cache.json'
$FreezePath = Join-Path $ReleaseRoot 'detector_freeze.json'
$Checkpoint = Join-Path $OutputRoot 'checkpoint.jsonl'
$LockPath = Join-Path $OutputRoot 'run.lock.json'
$LogRoot = Join-Path $OutputRoot 'logs'
$Tesseract = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$Tessdata = Join-Path $PipelineRoot 'tessdata'
$ExpectedVideos = 751
$MinimumFreeBytes = 10GB
$Release = 'temporal_detector_v0.4.0'
$Version = 'automatic-temporal-labeling-0.4.0'
$OwnLock = $false
$Child = $null
$StdoutTemp = $null
$StderrTemp = $null
$LogPath = $null

function Stop-WithError([string]$Message) { throw "ERROR DE PREVALIDACION: $Message" }
function Need-File([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Stop-WithError "No existe ${Name}: ${Path}" }
}
function Need-Dir([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { Stop-WithError "No existe ${Name}: ${Path}" }
}
function Get-ActiveRun {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'run_pipeline\.py' -and $_.CommandLine -match 'full_run_v0\.4\.0'
    }
}
function Read-Checkpoint([string]$Path) {
    $items = @(); if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $items }
    $line = 0
    foreach ($raw in Get-Content -LiteralPath $Path) {
        $line++; if ([string]::IsNullOrWhiteSpace($raw)) { continue }
        try { $items += ($raw | ConvertFrom-Json -ErrorAction Stop) }
        catch { Stop-WithError "checkpoint.jsonl invalido en la linea ${line}: $($_.Exception.Message)" }
    }
    return $items
}
function Get-Stats([object[]]$Items) {
    $accepted = 0; $excluded = 0
    foreach ($item in $Items) { $accepted += @($item.detections).Count; $excluded += @($item.excluded).Count }
    [pscustomobject]@{
        Completed = @($Items).Count
        Pending = [math]::Max(0, $ExpectedVideos - @($Items).Count)
        Failed = @($Items | Where-Object { $_.summary.status -eq 'failed' }).Count
        Accepted = $accepted; Excluded = $excluded
        Percent = (@($Items).Count / $ExpectedVideos) * 100
        LastId = if (@($Items).Count) { $Items[-1].id_video } else { '-' }
    }
}
function Emit([string]$Text) {
    $line = "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] $Text"
    Write-Host $line
    if ($LogPath) { Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8 }
}
function New-Text([string]$Path, [ref]$Offset) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    $all = [IO.File]::ReadAllText($Path)
    if ($all.Length -le $Offset.Value) { return '' }
    $new = $all.Substring($Offset.Value); $Offset.Value = $all.Length; return $new
}

try {
    Need-Dir $ProjectRoot 'proyecto FORTIA'
    Need-File $Python 'Python del backend'
    Need-Dir $PipelineRoot 'carpeta del pipeline temporal'
    Need-File $RunPipeline 'run_pipeline.py'; Need-File $Detector 'detector.py'; Need-File $Readme 'pipeline README'
    Need-Dir $OutputRoot 'carpeta de salida existente'; Need-Dir $ReleaseRoot 'carpeta de release congelada'
    Need-File $CachePath 'cache OCR versionada'; Need-File $FreezePath 'detector_freeze.json'
    Need-Dir $VideosRoot 'carpeta de videos de F:'; Need-File $VideoCsv 'inventario CSV de videos'
    Need-File $Tesseract 'ejecutable de Tesseract'; Need-Dir $Tessdata 'tessdata local'
    Need-File (Join-Path $Tessdata 'eng.traineddata') 'eng.traineddata local'
    Need-File (Join-Path $Tessdata 'spa.traineddata') 'spa.traineddata local'
    if (-not (Test-Path -LiteralPath 'F:\' -PathType Container)) { Stop-WithError 'la unidad F: no esta disponible' }

    $freeze = Get-Content -LiteralPath $FreezePath -Raw | ConvertFrom-Json
    if ([string]$freeze.release -ne $Release) { Stop-WithError "detector_freeze.json no corresponde a $Release" }
    if ([string]$freeze.detector_version -ne $Version) { Stop-WithError 'la version del detector no coincide con la congelada' }
    $source = Get-Content -LiteralPath $Detector -Raw
    if (($source -notmatch 'VERSION\s*=\s*') -or ($source -notmatch 'automatic-temporal-labeling-0\.4\.0')) { Stop-WithError 'detector.py no esta validado en v0.4.0' }
    $hashProperty = $freeze.file_hashes.PSObject.Properties | Where-Object { $_.Name -eq $RunPipeline }
    if ($hashProperty) {
        $actualHash = (Get-FileHash -LiteralPath $RunPipeline -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne ([string]$hashProperty.Value).ToLowerInvariant()) { Stop-WithError 'el hash de run_pipeline.py difiere del freeze' }
    }

    $pythonCheck = & $Python -c "import sys, cv2, pandas, pytesseract; print(sys.executable); print(cv2.__version__); print(pandas.__version__); print(pytesseract.get_tesseract_version())" 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-WithError "no se pueden importar las dependencias de Python: $($pythonCheck -join ' ')" }
    if (([string]$pythonCheck[0]).ToLowerInvariant() -ne $Python.ToLowerInvariant()) { Stop-WithError 'el ejecutable de Python no es el congelado del backend' }
    $rows = @(Import-Csv -LiteralPath $VideoCsv)
    if ($rows.Count -ne $ExpectedVideos) { Stop-WithError "el inventario tiene $($rows.Count) filas; se esperaban $ExpectedVideos" }
    $bad = @($rows | Where-Object { $_.ruta_video -notmatch '(?i)\.mp4$' -or -not (Test-Path -LiteralPath $_.ruta_video -PathType Leaf) })
    if ($bad.Count) { Stop-WithError "hay rutas ausentes o que no son MP4: $($bad.Count)" }
    $drive = Get-PSDrive -Name C -ErrorAction Stop
    if ($drive.Free -lt $MinimumFreeBytes) { Stop-WithError "espacio libre insuficiente en C: $([math]::Round($drive.Free / 1GB, 2)) GB" }

    $items = @(Read-Checkpoint $Checkpoint)
    $ids = @($items | ForEach-Object { [string]$_.id_video })
    if (@($ids | Sort-Object -Unique).Count -ne $ids.Count) { Stop-WithError 'el checkpoint contiene IDs de video duplicados' }
    $validIds = @($rows | ForEach-Object { [string]$_.id_video })
    if (@($ids | Where-Object { $_ -notin $validIds }).Count) { Stop-WithError 'el checkpoint contiene un ID fuera del inventario' }

    $active = @(Get-ActiveRun)
    if ($active.Count) {
        foreach ($p in $active) { Write-Host "El procesamiento ya esta activo. PID $($p.ProcessId). No se iniciara otra instancia."; Write-Host $p.CommandLine }
        exit 2
    }
    if (Test-Path -LiteralPath $LockPath -PathType Leaf) {
        $old = $null; try { $old = Get-Content $LockPath -Raw | ConvertFrom-Json } catch {}
        $oldPid = if ($old -and $old.pid) { Get-Process -Id ([int]$old.pid) -ErrorAction SilentlyContinue } else { $null }
        if ($oldPid) { Stop-WithError "lock belongs to active PID $($old.pid)" }
        Remove-Item -LiteralPath $LockPath -Force
    }

    New-Item -ItemType File -LiteralPath $LockPath -Force:$false | Out-Null; $OwnLock = $true
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    $started = Get-Date
    $LogPath = Join-Path $LogRoot ("temporal_{0}.log" -f $started.ToString('yyyyMMdd_HHmmss'))
    $command = "`"$Python`" run_pipeline.py --sample-fps 1 --refine-fps 12 --output `"$OutputRoot`" --ocr-cache `"$CachePath`" --ocr-cache-mode use --resume"
    $lock = [ordered]@{ pid=$PID; child_pid=$null; started_at=$started.ToString('o'); detector_release=$Release; detector_version=$Version; run_id=[guid]::NewGuid().ToString(); command=$command; output=$OutputRoot }
    $lock | ConvertTo-Json | Set-Content -LiteralPath $LockPath -Encoding UTF8
    Emit "Inicio del etiquetado temporal. Detector $Release ($Version)"
    Emit "Python: $Python"; Emit "Videos: $VideosRoot"; Emit "Salida: $OutputRoot"
    Emit 'Configuracion: sample_fps=1; refine_fps=12; ocr_cache_mode=use; resume=true'
    Emit "Checkpoint: $Checkpoint; completados=$($items.Count); ultimo=$((Get-Stats $items).LastId)"
    Emit "Comando: $command"

    $StdoutTemp = Join-Path $OutputRoot ".stdout_$PID.tmp"; $StderrTemp = Join-Path $OutputRoot ".stderr_$PID.tmp"
    $args = @('run_pipeline.py','--sample-fps','1','--refine-fps','12','--output',$OutputRoot,'--ocr-cache',$CachePath,'--ocr-cache-mode','use','--resume')
    $Child = Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $PipelineRoot -NoNewWindow -PassThru -RedirectStandardOutput $StdoutTemp -RedirectStandardError $StderrTemp
    $lock.child_pid = $Child.Id; $lock | ConvertTo-Json | Set-Content -LiteralPath $LockPath -Encoding UTF8
    Emit "PID del pipeline: $($Child.Id)"
    $outOffset=0; $errOffset=0; $lastReport=[datetime]::MinValue
    while (-not $Child.HasExited) {
        foreach ($entry in @(@{Path=$StdoutTemp; Offset=[ref]$outOffset; Prefix=''}, @{Path=$StderrTemp; Offset=[ref]$errOffset; Prefix='[stderr] '})) {
            $new = New-Text $entry.Path $entry.Offset
            foreach ($line in ($new -split "`r?`n")) { if ($line) { Emit ($entry.Prefix + $line) } }
        }
        if (((Get-Date)-$lastReport).TotalSeconds -ge 30) {
            $now = @(Read-Checkpoint $Checkpoint); $s=Get-Stats $now; $proc=Get-Process -Id $Child.Id -ErrorAction SilentlyContinue
            $memory=if($proc){[math]::Round($proc.WorkingSet64/1MB,1)}else{0}
            Emit ("Progreso: {0}/{1} ({2:N2}%), pendientes={3}, fallidos={4}, eventos={5}, excluidos={6}, ultimo={7}, memoria={8} MB" -f $s.Completed,$ExpectedVideos,$s.Percent,$s.Pending,$s.Failed,$s.Accepted,$s.Excluded,$s.LastId,$memory)
            $lastReport=Get-Date
        }
        Start-Sleep -Seconds 5
    }
    foreach ($entry in @(@{Path=$StdoutTemp; Offset=[ref]$outOffset; Prefix=''}, @{Path=$StderrTemp; Offset=[ref]$errOffset; Prefix='[stderr] '})) {
        $new=New-Text $entry.Path $entry.Offset; foreach($line in ($new -split "`r?`n")){if($line){Emit($entry.Prefix+$line)}}
    }
    $final=@(Read-Checkpoint $Checkpoint); $s=Get-Stats $final
    Emit "Fin. Codigo de salida=$($Child.ExitCode)"; Emit ("Resultado: completados={0}, pendientes={1}, fallidos={2}, eventos={3}, excluidos={4}, duracion={5}" -f $s.Completed,$s.Pending,$s.Failed,$s.Accepted,$s.Excluded,((Get-Date)-$started)); Emit "Log: $LogPath"
    if ($Child.ExitCode -ne 0) { throw "run_pipeline.py termino con codigo $($Child.ExitCode)" }
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($LogPath) { Add-Content -LiteralPath $LogPath -Value "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] $($_.Exception.Message)" -Encoding UTF8 }
    exit 1
}
finally {
    if ($Child -and -not $Child.HasExited) { Write-Host 'El proceso hijo sigue activo; se conserva el bloqueo.' -ForegroundColor Yellow }
    elseif ($OwnLock -and (Test-Path -LiteralPath $LockPath)) { Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue }
    foreach ($tmp in @($StdoutTemp,$StderrTemp)) { if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue } }
    Write-Host 'La consola permanecera abierta. Presiona Enter para cerrar.'
    [void](Read-Host)
}
