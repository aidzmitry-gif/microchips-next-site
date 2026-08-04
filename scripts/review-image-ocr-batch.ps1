[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ManifestPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputPath,

    [string[]]$OcrLanguage = @('en-US', 'ru-RU')
)

# Windows PowerShell 5.1 only. This script is an evidence-review helper: it
# never derives an expectation from a filename and never contacts a database.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-WindowsPowerShell51 {
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5) {
        throw 'This helper requires Windows PowerShell 5.1 (Desktop edition).'
    }
    $languages = @($OcrLanguage | Sort-Object -Unique)
    if ($languages.Count -ne 2 -or $languages[0] -ne 'en-US' -or $languages[1] -ne 'ru-RU') {
        throw 'Specify exactly both OCR languages: -OcrLanguage en-US,ru-RU.'
    }
}

function Initialize-WindowsOcr {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime]
    $null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
}

function Wait-WinRtOperation {
    param(
        [Parameter(Mandatory = $true)]$Operation,
        [Parameter(Mandatory = $true)][Type]$ResultType
    )

    # PowerShell 5.1 cannot infer TResult when it invokes the generic WinRT
    # extension method directly. WinRT proxies are System.__ComObject and do
    # not expose their generic interfaces through GetType(), so every caller
    # supplies the known TResult from its WinRT API signature.
    $asTask = @([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.GetGenericTypeDefinition().FullName -eq 'Windows.Foundation.IAsyncOperation`1'
    }) | Select-Object -First 1
    if ($null -eq $asTask) {
        throw 'Generic WinRT AsTask<TResult>(IAsyncOperation<TResult>) bridge is unavailable.'
    }
    $task = $asTask.MakeGenericMethod(@($ResultType)).Invoke($null, @($Operation))
    return $task.GetAwaiter().GetResult()
}

function Get-OcrEngines {
    $engines = @()
    foreach ($languageTag in $OcrLanguage) {
        $language = [Windows.Globalization.Language]::new($languageTag)
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
        if ($null -eq $engine) {
            throw "OCR language is unavailable: $languageTag"
        }
        $engines += $engine
    }
    return $engines
}

function Get-OcrText {
    param(
        [Parameter(Mandatory = $true)][string]$ImagePath,
        [Parameter(Mandatory = $true)][object[]]$Engines
    )

    $file = $null
    $stream = $null
    $bitmap = $null
    try {
        $file = Wait-WinRtOperation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
        $stream = Wait-WinRtOperation ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Wait-WinRtOperation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Wait-WinRtOperation ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $texts = foreach ($engine in $Engines) {
            (Wait-WinRtOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])).Text
        }
        return [string]::Join("`n", [string[]]$texts)
    }
    finally {
        if ($null -ne $bitmap -and $bitmap -is [System.IDisposable]) { $bitmap.Dispose() }
        if ($null -ne $stream -and $stream -is [System.IDisposable]) { $stream.Dispose() }
    }
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Text)

    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    return ([System.BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
}

function ConvertTo-NormalizedTokens {
    param([Parameter(Mandatory = $true)][string]$Text)

    $upper = $Text.Normalize([Text.NormalizationForm]::FormKC).ToUpperInvariant()
    $tokens = [regex]::Matches($upper, '[\p{L}\p{Nd}]+') | ForEach-Object { $_.Value }
    return @($tokens)
}

function Test-ExactBoundedMpnMatch {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$OcrTokens,
        [Parameter(Mandatory = $true)][string]$ExpectedExact
    )

    $expectedTokens = @(ConvertTo-NormalizedTokens $ExpectedExact)
    if ($expectedTokens.Count -eq 0) {
        return $false
    }
    for ($start = 0; $start -le $OcrTokens.Count - $expectedTokens.Count; $start++) {
        $matched = $true
        for ($offset = 0; $offset -lt $expectedTokens.Count; $offset++) {
            if ($OcrTokens[$start + $offset] -cne $expectedTokens[$offset]) {
                $matched = $false
                break
            }
        }
        if ($matched) {
            return $true
        }
    }
    return $false
}

function Get-ExpectedExactValue {
    param([Parameter(Mandatory = $true)]$Row)

    $mpn = if ($null -ne $Row.PSObject.Properties['expected_mpn']) { [string]$Row.expected_mpn } else { '' }
    $modelCore = if ($null -ne $Row.PSObject.Properties['expected_model_core']) { [string]$Row.expected_model_core } else { '' }
    if (-not [string]::IsNullOrWhiteSpace($mpn) -and -not [string]::IsNullOrWhiteSpace($modelCore)) {
        throw 'manifest row has both expected_mpn and expected_model_core'
    }
    if (-not [string]::IsNullOrWhiteSpace($mpn)) { return $mpn.Trim() }
    if (-not [string]::IsNullOrWhiteSpace($modelCore)) { return $modelCore.Trim() }
    throw 'manifest row has no expected_mpn or expected_model_core'
}

if ($MyInvocation.InvocationName -eq '.') {
    return
}

Assert-WindowsPowerShell51
$resolvedManifest = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ManifestPath)
$resolvedOutput = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
if (-not (Test-Path -LiteralPath $resolvedManifest -PathType Leaf)) {
    throw "OCR manifest was not found: $resolvedManifest"
}
$manifest = @(Import-Csv -LiteralPath $resolvedManifest -Encoding UTF8)
if ($manifest.Count -eq 0) { throw 'OCR manifest is empty.' }
$headers = @((Get-Content -LiteralPath $resolvedManifest -Encoding UTF8 -TotalCount 1).Split(','))
if ($headers -notcontains 'image_path' -or (($headers -notcontains 'expected_mpn') -and ($headers -notcontains 'expected_model_core'))) {
    throw 'OCR manifest requires image_path and expected_mpn or expected_model_core headers.'
}

Initialize-WindowsOcr
$engines = Get-OcrEngines
$outputRows = @(foreach ($row in $manifest) {
    $imagePath = [string]$row.image_path
    $expectedExact = ''
    try {
        $expectedExact = Get-ExpectedExactValue $row
        if ([string]::IsNullOrWhiteSpace($imagePath)) { throw 'manifest row has no image_path' }
        $resolvedImage = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($imagePath)
        if (-not (Test-Path -LiteralPath $resolvedImage -PathType Leaf)) { throw 'local_image_not_found' }
        $text = Get-OcrText -ImagePath $resolvedImage -Engines $engines
        $tokens = @(ConvertTo-NormalizedTokens $text)
        $isMatch = Test-ExactBoundedMpnMatch -OcrTokens $tokens -ExpectedExact $expectedExact
        [pscustomobject][ordered]@{
            image_path = $imagePath
            expected_exact = $expectedExact
            ocr_text_sha256 = Get-Sha256Hex $text
            ocr_normalized_tokens = [string]::Join(' ', [string[]]$tokens)
            verdict = if ($isMatch) { 'PASS' } else { 'HOLD' }
            hold_reason = if ($isMatch) { '' } else { 'exact_bounded_expected_token_sequence_not_found' }
            ocr_languages = [string]::Join('|', $OcrLanguage)
        }
    }
    catch {
        [pscustomobject][ordered]@{
            image_path = $imagePath
            expected_exact = $expectedExact
            ocr_text_sha256 = ''
            ocr_normalized_tokens = ''
            verdict = 'HOLD'
            hold_reason = ('ocr_or_input_error:' + $_.Exception.Message).Replace("`r", ' ').Replace("`n", ' ')
            ocr_languages = [string]::Join('|', $OcrLanguage)
        }
    }
})

$outputDirectory = Split-Path -Parent $resolvedOutput
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
}
$outputRows | Export-Csv -LiteralPath $resolvedOutput -NoTypeInformation -Encoding UTF8
Write-Host "OCR review complete: $($outputRows.Count) rows; output: $resolvedOutput"
