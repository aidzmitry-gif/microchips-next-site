[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot '..\review-image-ocr-batch.ps1'
$text = [System.IO.File]::ReadAllText($scriptPath, [System.Text.UTF8Encoding]::new($false))

foreach ($required in @('Windows.Media.Ocr.OcrEngine', "'en-US'", "'ru-RU'", 'Get-Sha256Hex', 'Test-ExactBoundedMpnMatch', "'PASS'", "'HOLD'", 'Export-Csv', '-Encoding UTF8')) {
    if ($text -notlike "*$required*") { throw "Missing OCR safety contract: $required" }
}
foreach ($forbidden in @('Invoke-WebRequest', 'Invoke-RestMethod', 'docker', 'artisan', 'Publish-', 'Update-Database', 'GetFileName(')) {
    if ($text -match [regex]::Escape($forbidden)) { throw "Forbidden operation in OCR helper: $forbidden" }
}

. $scriptPath -ManifestPath '__not_executed__' -OutputPath '__not_executed__'
if (-not (Test-ExactBoundedMpnMatch -OcrTokens @('FANSO', 'ER14505H', '3', '6', 'V') -ExpectedExact 'ER14505H')) {
    throw 'Exact contiguous MPN match must pass.'
}
if (-not (Test-ExactBoundedMpnMatch -OcrTokens @('PANASONIC', 'BR', '2', '3A') -ExpectedExact 'BR-2/3A')) {
    throw 'Delimited model-core sequence must pass.'
}
if (Test-ExactBoundedMpnMatch -OcrTokens @('ER14505', 'H') -ExpectedExact 'ER14505H') {
    throw 'Split OCR tokens must not be inferred into an MPN.'
}

# Raster OCR remains optional because Windows.Media.Ocr language packs are a
# host capability, not a repository dependency. When the checked-in local
# Wave225 assets are available, run one real WinRT OCR decode/recognition
# smoke: the verdict may be PASS or HOLD, but bridge/decode errors are not.
$asset = Join-Path $PSScriptRoot '..\..\.tmp\wave225-assets\1993.png'
if (Test-Path -LiteralPath $asset -PathType Leaf) {
    $smokeDirectory = Join-Path $PSScriptRoot '..\..\.tmp\wave225-ocr-smoke'
    [System.IO.Directory]::CreateDirectory($smokeDirectory) | Out-Null
    $smokeManifest = Join-Path $smokeDirectory 'input.csv'
    $smokeOutput = Join-Path $smokeDirectory 'output.csv'
    [System.IO.File]::WriteAllText($smokeManifest, "image_path,expected_mpn`r`n$asset,CR2`r`n", [System.Text.Encoding]::UTF8)
    & $scriptPath -ManifestPath $smokeManifest -OutputPath $smokeOutput
    $smoke = @(Import-Csv -LiteralPath $smokeOutput -Encoding UTF8)
    if ($smoke.Count -ne 1 -or $smoke[0].verdict -notin @('PASS', 'HOLD') -or -not $smoke[0].ocr_text_sha256 -or $smoke[0].hold_reason -like 'ocr_or_input_error:*') {
        throw 'Real Windows.Media.Ocr smoke did not produce a decoded review result.'
    }
}

# These synthetic sequences exercise the exact, bounded PASS/HOLD decision
# without faking OCR output.
Write-Host 'OCR helper static safety contract passed.'
