param(
    [string]$BaseUrl = 'https://microchips.by',
    [string]$OutputDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated\public-seo-snapshot'),
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = 'Stop'

$priorityPaths = @(
    '/',
    '/robots.txt',
    '/sitemap.xml',
    '/sitemap-files.xml',
    '/sitemap-iblock-26.xml',
    '/aspro-sitemap/sitemap-1.xml',
    '/catalog/',
    '/catalog/akkumulyatory/',
    '/catalog/akkumulyatory/promyshlennye/',
    '/catalog/akkumulyatory/dlya_ibp/',
    '/catalog/akkumulyatory/dlya_ibp/apc/',
    '/catalog/akkumulyatory/promyshlennye/dlya-telekommunikatsiy/48-v/',
    '/catalog/akkumulyatory/dlya_ibp/1543/',
    '/catalog/mikroelektronika/aktivnye_elementy/mikroskhemy/',
    '/contacts/'
)

function Get-TextFromHtml {
    param([string]$Value)

    if (-not $Value) {
        return ''
    }

    $withoutTags = $Value -replace '(?is)<[^>]+>', ' '
    return [System.Net.WebUtility]::HtmlDecode(($withoutTags -replace '\s+', ' ').Trim())
}

function Get-FirstMatchValue {
    param(
        [string]$Text,
        [string]$Pattern,
        [string]$Group = 'value'
    )

    $match = [regex]::Match($Text, $Pattern)
    if ($match.Success) {
        return Get-TextFromHtml -Value $match.Groups[$Group].Value
    }

    return ''
}

function Get-PublicUrlSnapshot {
    param(
        [string]$Path,
        [int]$Index
    )

    $url = ([Uri]::new([Uri]$BaseUrl, $Path)).AbsoluteUri
    $prefix = '{0:D2}' -f $Index
    $headersPath = Join-Path $OutputDir "$prefix.headers.txt"
    $bodyPath = Join-Path $OutputDir "$prefix.body.txt"
    $metricsPath = Join-Path $OutputDir "$prefix.metrics.txt"

    $metrics = & curl.exe `
        --silent --show-error --location `
        --connect-timeout 10 --max-time $TimeoutSeconds `
        --user-agent 'MicrochipsMigrationAudit/1.0 (+read-only; no-cookies)' `
        --dump-header $headersPath --output $bodyPath `
        --write-out '%{http_code}|%{url_effective}|%{num_redirects}' `
        $url

    if ($LASTEXITCODE -ne 0) {
        return [PSCustomObject]@{
            requested_url      = $url
            final_url          = ''
            http_status        = ''
            redirect_hops      = ''
            redirect_locations = ''
            canonical          = ''
            robots             = ''
            title              = ''
            h1                 = ''
            result             = 'request_failed'
        }
    }

    $metricParts = ([string]$metrics).Trim() -split '\|', 3
    $headers = Get-Content -LiteralPath $headersPath -Raw -Encoding utf8
    $body = Get-Content -LiteralPath $bodyPath -Raw -Encoding utf8
    $locations = [regex]::Matches($headers, '(?im)^location:\s*(?<value>.+)$') |
        ForEach-Object { $_.Groups['value'].Value.Trim() }

    return [PSCustomObject]@{
        requested_url      = $url
        final_url          = if ($metricParts.Count -gt 1) { $metricParts[1] } else { '' }
        http_status        = if ($metricParts.Count -gt 0) { $metricParts[0] } else { '' }
        redirect_hops      = if ($metricParts.Count -gt 2) { $metricParts[2] } else { '' }
        redirect_locations = $locations -join ' | '
        canonical          = Get-FirstMatchValue -Text $body -Pattern '(?is)<link\b(?=[^>]*\brel\s*=\s*["'']?canonical\b)(?=[^>]*\bhref\s*=\s*["''](?<value>[^"'']+))[^^>]*>'
        robots             = Get-FirstMatchValue -Text $body -Pattern '(?is)<meta\b(?=[^>]*\bname\s*=\s*["'']?robots\b)(?=[^>]*\bcontent\s*=\s*["''](?<value>[^"'']+))[^^>]*>'
        title              = Get-FirstMatchValue -Text $body -Pattern '(?is)<title[^>]*>(?<value>.*?)</title>'
        h1                 = Get-FirstMatchValue -Text $body -Pattern '(?is)<h1[^>]*>(?<value>.*?)</h1>'
        result             = 'captured'
    }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$rows = for ($index = 0; $index -lt $priorityPaths.Count; $index++) {
    Get-PublicUrlSnapshot -Path $priorityPaths[$index] -Index $index
}

$rows | Export-Csv -LiteralPath (Join-Path $OutputDir 'priority-url-snapshot.csv') -NoTypeInformation -Encoding utf8

[PSCustomObject]@{
    captured_at           = (Get-Date).ToString('o')
    base_url              = $BaseUrl
    priority_urls         = $rows.Count
    captured_urls         = @($rows | Where-Object result -eq 'captured').Count
    failed_urls           = @($rows | Where-Object result -ne 'captured').Count
    redirects_observed    = @($rows | Where-Object { [int]$_.redirect_hops -gt 0 }).Count
    output_directory      = $OutputDir
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'summary.json') -Encoding utf8

Write-Output "Created $OutputDir"
Write-Output "Captured $(@($rows | Where-Object result -eq 'captured').Count) of $($rows.Count) priority URLs"
