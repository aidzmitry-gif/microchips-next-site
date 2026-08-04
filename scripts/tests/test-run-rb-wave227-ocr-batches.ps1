[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '..\run-rb-wave227-ocr-batches.ps1'
$text = [System.IO.File]::ReadAllText($path, [System.Text.UTF8Encoding]::new($false))
foreach ($required in @('review-image-ocr-batch.ps1', 'Refusing to overwrite prior OCR review', 'database_apply', 'media_promotion', 'Sort-Object batch')) {
    if ($text -notlike "*$required*") { throw "Missing Wave227 batch-driver contract: $required" }
}
foreach ($forbidden in @('docker', 'artisan', 'Invoke-WebRequest', 'Invoke-RestMethod', 'Publish-', 'Update-Database')) {
    if ($text -match [regex]::Escape($forbidden)) { throw "Forbidden operation in Wave227 driver: $forbidden" }
}
Write-Host 'Wave227 OCR driver static safety contract passed.'
