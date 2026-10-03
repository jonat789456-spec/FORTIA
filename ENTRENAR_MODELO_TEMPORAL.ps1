[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\jonat\Downloads\FORTNITE IA 2'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$DataRoot = Join-Path $ProjectRoot 'backend\data\automatic_temporal_annotations'
$OutputRoot = Join-Path $ProjectRoot 'backend\artifacts\temporal_candidates'
$Coverage = Join-Path $DataRoot 'full_run_v0.4.0\coverage_summary.json'
$FinalReport = Join-Path $DataRoot 'full_run_v0.4.0\FINAL_TEMPORAL_DATASET_REPORT.json'
$Windows = Join-Path $DataRoot 'full_run_v0.4.0\predictive_windows_manifest.csv'
$Freeze = Join-Path $DataRoot 'release_v0.4.0\detector_freeze.json'
$Splits = Join-Path $ProjectRoot 'backend\data\splits'
$TestMarkers = @('test','test_used','test_metrics','test_predictions')

function Reject([string]$Message) {
    throw "ENTRENAMIENTO RECHAZADO: $Message"
}
function NeedFile([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Reject "falta ${Name}: ${Path}" }
}

try {
    NeedFile $Coverage 'coverage_summary.json de v0.4.0'
    NeedFile $FinalReport 'reporte final del dataset'
    NeedFile $Windows 'manifiesto de ventanas'
    NeedFile $Freeze 'freeze de v0.4.0'

    $coverage = Get-Content -Raw -LiteralPath $Coverage | ConvertFrom-Json
    if ([int]$coverage.videos_processed -lt 751 -or [int]$coverage.videos_failed -ne 0) {
        Reject "faltan videos por procesar o existen fallos: procesados=$($coverage.videos_processed), fallidos=$($coverage.videos_failed)"
    }
    $final = Get-Content -Raw -LiteralPath $FinalReport | ConvertFrom-Json
    if ([string]$final.status -notin @('DATOS TEMPORALES SUFICIENTES PARA ENTRENAR','DATOS TEMPORALES PARCIALMENTE SUFICIENTES')) {
        Reject "el dataset no declara suficiencia autorizada"
    }
    if ([bool]$final.windows_contaminated -or [bool]$final.test_used -or [bool]$final.hashes_match -eq $false) {
        Reject 'ventanas contaminadas, uso de test o hashes incompatibles'
    }
    if (-not (Test-Path -LiteralPath $Splits -PathType Container)) { Reject 'faltan los splits' }
    $splitFiles = @(Get-ChildItem -LiteralPath $Splits -File -ErrorAction SilentlyContinue)
    if ($splitFiles.Count -lt 2) { Reject 'faltan archivos de train/validation' }
    $rawFinal = Get-Content -Raw -LiteralPath $FinalReport
    foreach ($marker in $TestMarkers) {
        if ($rawFinal -match [regex]::Escape($marker)) { Reject "el reporte contiene marcador prohibido: $marker" }
    }
    if (@(Import-Csv -LiteralPath $Windows).Count -eq 0) { Reject 'no hay ventanas temporales válidas' }

    New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
    $manifest = [ordered]@{
        status = 'PREPARADO_NO_EJECUTADO'
        allowed_splits = @('train','validation')
        forbidden_split = 'test'
        candidates = @('direct_neutral','hierarchical_neutral_then_event')
        weighting = @('none','moderate','smoothed','limited')
        extreme_victory_weights = $false
        output_root = $OutputRoot
        source_freeze = $Freeze
        metrics = @('macro_f1','per_class_precision_recall_f1','balanced_accuracy','confusion_matrix','pr_auc','brier_score','calibration','false_alerts_per_minute','missed_events','anticipation_seconds','temporal_stability','horizon_performance','latency_mean','latency_p95')
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputRoot 'training_manifest.json') -Encoding UTF8
    Write-Host 'PREPARADO: faltan las implementaciones de candidatos y la autorización explícita para ejecutar.'
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
