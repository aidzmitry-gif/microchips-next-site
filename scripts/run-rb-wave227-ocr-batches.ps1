[CmdletBinding()]
param(
    [string]$IndexPath = ".\docs\audits\generated\wave227-ocr-batches\index.json"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$indexAbsolute = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IndexPath)
if (-not (Test-Path -LiteralPath $indexAbsolute -PathType Leaf)) { throw "OCR batch index not found: $indexAbsolute" }
$index = Get-Content -LiteralPath $indexAbsolute -Raw -Encoding UTF8 | ConvertFrom-Json
if ($index.policy.ocr_executed -ne $false -or $index.policy.database_apply -ne $false -or $index.policy.media_promotion -ne $false) { throw 'OCR batch index has an unsafe policy.' }
foreach ($batch in @($index.batches | Sort-Object batch)) {
    $input = Join-Path $root $batch.input
    $review = Join-Path $root $batch.review
    if (Test-Path -LiteralPath $review -PathType Leaf) { throw "Refusing to overwrite prior OCR review: $review" }
    & (Join-Path $PSScriptRoot 'review-image-ocr-batch.ps1') -ManifestPath $input -OutputPath $review
    if (-not $?) { throw "OCR batch failed: $($batch.batch)" }
}
Write-Host "Wave227 local OCR complete: $(@($index.batches).Count) batches; no database or media action was performed."
