[CmdletBinding()]
param(
    [string]$ExportPath = ".\docs\audits\generated\rb-wave227-legacy-preview-candidates.csv",
    [string]$AssetsRoot = ".\.tmp\wave227-assets"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$resolvedExport = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ExportPath)
$resolvedAssets = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($AssetsRoot)
if (-not (Test-Path -LiteralPath $resolvedExport -PathType Leaf)) { throw "Exporter CSV was not found: $resolvedExport" }
$rows = @(Import-Csv -LiteralPath $resolvedExport -Encoding UTF8)
if ($rows.Count -eq 0) { throw 'Exporter CSV is empty.' }
$required = @('external_id','media_id','storage_path','content_sha256','rights_basis','identity_scope','mpn','model_core','manufacturer')
if ((Compare-Object $required @($rows[0].PSObject.Properties.Name) -SyncWindow 0)) { throw 'Exporter CSV field contract drift.' }

$storagePaths = [System.Collections.Generic.List[string]]::new()
foreach ($row in $rows) {
    $path = ([string]$row.storage_path).Replace('\', '/')
    if ([string]::IsNullOrWhiteSpace($path) -or $path.StartsWith('/') -or $path.Split('/') -contains '..') { throw "Unsafe exporter storage path: $path" }
    if (-not ([string]$row.content_sha256 -match '^[a-f0-9]{64}$')) { throw "Invalid exporter hash: $($row.media_id)" }
    $storagePaths.Add($path)
}
$storagePaths = @($storagePaths | Sort-Object -Unique)

[System.IO.Directory]::CreateDirectory($resolvedAssets) | Out-Null
$listPath = Join-Path $resolvedAssets 'wave227-exported-storage-paths.txt'
$archivePath = Join-Path $resolvedAssets 'wave227-exported-assets.tar'
# GNU tar's -T parser treats CR as part of a POSIX filename. Use LF explicitly
# even though this helper runs in Windows PowerShell.
[System.IO.File]::WriteAllText($listPath, ([string]::Join("`n", [string[]]$storagePaths) + "`n"), [System.Text.UTF8Encoding]::new($false))
$container = (& docker compose ps -q backend).Trim()
if (-not $container) { throw 'Docker backend container is not running.' }
$containerList = '/tmp/wave227-exported-storage-paths.txt'
$containerArchive = '/tmp/wave227-exported-assets.tar'

# One container exec creates a single archive under the storage root. docker cp
# transfers the list and one archive; no per-file request and no network call.
& docker cp $listPath "${container}:$containerList"
if ($LASTEXITCODE -ne 0) { throw 'Could not copy the export path list into backend container.' }
& docker compose exec -T backend sh -lc "set -eu; cd /var/www/storage/app/public; tar -cf $containerArchive -T $containerList"
if ($LASTEXITCODE -ne 0) { throw 'Could not archive exported backend assets.' }
& docker cp "${container}:$containerArchive" $archivePath
if ($LASTEXITCODE -ne 0) { throw 'Could not copy exported backend asset archive.' }
& tar -xf $archivePath -C $resolvedAssets
if ($LASTEXITCODE -ne 0) { throw 'Could not extract exported backend asset archive.' }

foreach ($row in $rows) {
    $path = Join-Path $resolvedAssets ([string]$row.storage_path)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Materialized asset is missing: $($row.media_id)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne ([string]$row.content_sha256).ToLowerInvariant()) { throw "Materialized asset hash mismatch: $($row.media_id)" }
}
Write-Host "Wave227 assets materialized and SHA-256 verified: $($rows.Count) files. No database or media state was changed."
