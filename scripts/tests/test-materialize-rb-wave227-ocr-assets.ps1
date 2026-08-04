[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '..\materialize-rb-wave227-ocr-assets.ps1'
$text = [System.IO.File]::ReadAllText($path, [System.Text.UTF8Encoding]::new($false))
foreach ($required in @('docker compose exec -T backend', 'docker cp', 'tar -cf', 'Get-FileHash', 'content_sha256', 'No database or media state was changed')) {
    if ($text -notlike "*$required*") { throw "Missing Wave227 asset-materialization contract: $required" }
}
foreach ($forbidden in @('Invoke-WebRequest', 'Invoke-RestMethod', 'artisan', 'Publish-', 'Update-Database')) {
    if ($text -match [regex]::Escape($forbidden)) { throw "Forbidden operation in Wave227 materializer: $forbidden" }
}
Write-Host 'Wave227 OCR asset materializer static safety contract passed.'
