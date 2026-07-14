param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [string]$OutputDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated')
)

$ErrorActionPreference = 'Stop'
$frontArchive = Join-Path $SourceRoot 'microchips_fronts_20260623.tar.gz'
$publicRoot = 'microchips.by/public_html/'

if (-not (Test-Path -LiteralPath $frontArchive)) {
    throw "Front archive is missing: $frontArchive"
}

function Get-ArchiveContent {
    param([string]$Entry)

    $content = [string]::Concat([string[]] @(& tar -xOzf $script:frontArchive $Entry))
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read archive entry: $Entry"
    }

    return $content
}

function Get-SitemapRows {
    param(
        [string]$Entry,
        [string]$Source,
        [string]$PreliminaryType
    )

    $content = Get-ArchiveContent -Entry (Join-Path $script:publicRoot $Entry).Replace('\', '/')

    foreach ($match in [regex]::Matches($content, '<loc>(?<url>[^<]+)</loc>')) {
        [PSCustomObject]@{
            old_url          = $match.Groups['url'].Value
            source           = $Source
            preliminary_type = $PreliminaryType
            decision         = 'unreviewed'
            new_url          = ''
            owner            = ''
            status           = 'pending'
        }
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$coreUrls = @(Get-SitemapRows -Entry 'sitemap-iblock-26.xml' -Source 'sitemap-iblock-26.xml' -PreliminaryType 'catalog_core')
$asproUrls = @(Get-SitemapRows -Entry 'aspro-sitemap/sitemap-1.xml' -Source 'aspro-sitemap/sitemap-1.xml' -PreliminaryType 'seo_landing_candidate')
@($coreUrls + $asproUrls) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'legacy-url-inventory.csv') -NoTypeInformation -Encoding utf8

$htaccess = Get-ArchiveContent -Entry ($publicRoot + '.htaccess')
$directives = [regex]::Matches(
    $htaccess,
    '(?i)(?<![A-Za-z])(?<directive>RedirectMatch|Redirect)\s+301\s+(?<source>\S+)\s+'
)
$redirectRows = for ($index = 0; $index -lt $directives.Count; $index++) {
    $directive = $directives[$index]
    $segmentStart = $directive.Index + $directive.Length
    $segmentEnd = if ($index -lt ($directives.Count - 1)) { $directives[$index + 1].Index } else { $htaccess.Length }
    $segment = $htaccess.Substring($segmentStart, $segmentEnd - $segmentStart)
    $target = [regex]::Match($segment, '(?<target>https?://[^\s<]+|/[^\s<]+)').Groups['target'].Value

    [PSCustomObject]@{
        directive       = $directive.Groups['directive'].Value
        old_url_pattern = $directive.Groups['source'].Value
        target_raw      = $target
        decision        = 'needs_review'
        final_url       = ''
        owner           = ''
        status          = if ($target) { 'extracted' } else { 'parse_error' }
    }
}
$redirectRows |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'legacy-redirect-source.csv') -NoTypeInformation -Encoding utf8

[PSCustomObject]@{
    generated_at             = (Get-Date).ToString('o')
    source_root              = $SourceRoot
    core_sitemap_urls        = $coreUrls.Count
    seo_landing_candidate_urls = $asproUrls.Count
    redirects_extracted      = $redirectRows.Count
    redirect_parse_errors    = @($redirectRows | Where-Object status -eq 'parse_error').Count
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'summary.json') -Encoding utf8

Write-Output "Created $OutputDir"
Write-Output "Legacy URLs: $($coreUrls.Count + $asproUrls.Count)"
Write-Output "Legacy redirects: $($redirectRows.Count)"
