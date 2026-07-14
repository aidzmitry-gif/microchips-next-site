[CmdletBinding()]
param(
    [string]$InventoryPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated\legacy-url-inventory.csv'),
    [string]$RedirectSourcePath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated\legacy-redirect-source.csv'),
    [string]$OutputDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated'),
    [string[]]$AllowedHost = @('microchips.by', 'www.microchips.by'),
    [switch]$RunSelfTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-Condition {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw "Self-test failed: $Message"
    }
}

function Get-PathDetails {
    param(
        [AllowEmptyString()]
        [string]$Url,
        [string[]]$TrustedHosts
    )

    $result = [ordered]@{
        is_valid          = $false
        normalized_path   = ''
        host              = ''
        has_query_or_hash = $false
        issue             = ''
    }

    if ([string]::IsNullOrWhiteSpace($Url)) {
        $result.issue = 'empty_url'
        return [PSCustomObject]$result
    }

    try {
        $uri = [System.Uri]::new($Url, [System.UriKind]::Absolute)
    }
    catch {
        $result.issue = 'invalid_absolute_url'
        return [PSCustomObject]$result
    }

    if ($uri.Scheme -notin @('http', 'https')) {
        $result.issue = 'unsupported_scheme'
        return [PSCustomObject]$result
    }

    $parsedHost = $uri.Host.ToLowerInvariant()
    $result.host = $parsedHost
    if ($TrustedHosts -notcontains $parsedHost) {
        $result.issue = 'untrusted_host'
        return [PSCustomObject]$result
    }

    $path = $uri.AbsolutePath
    if ([string]::IsNullOrWhiteSpace($path)) {
        $path = '/'
    }
    $path = [regex]::Replace($path, '/{2,}', '/')
    if ($path -ne '/' -and -not $path.EndsWith('/')) {
        $path = "$path/"
    }

    $result.is_valid = $true
    $result.normalized_path = $path
    $result.has_query_or_hash = ($uri.Query.Length -gt 0 -or $uri.Fragment.Length -gt 0)
    return [PSCustomObject]$result
}

function Get-RelativePathDetails {
    param(
        [AllowEmptyString()]
        [string]$Path
    )

    $result = [ordered]@{
        is_valid        = $false
        normalized_path = ''
    }

    if ([string]::IsNullOrWhiteSpace($Path) -or -not $Path.StartsWith('/')) {
        return [PSCustomObject]$result
    }

    $pathWithoutQuery = ($Path -split '[?#]', 2)[0]
    if ($pathWithoutQuery -match '[\(\)\[\]\{\}\^\$\*\+\|\\]') {
        return [PSCustomObject]$result
    }

    $pathWithoutQuery = [regex]::Replace($pathWithoutQuery, '/{2,}', '/')
    if ($pathWithoutQuery -ne '/' -and -not $pathWithoutQuery.EndsWith('/')) {
        $pathWithoutQuery = "$pathWithoutQuery/"
    }

    $result.is_valid = $true
    $result.normalized_path = $pathWithoutQuery
    return [PSCustomObject]$result
}

function Test-IsStaticRedirectSource {
    param(
        [string]$Directive,
        [AllowEmptyString()]
        [string]$SourcePattern
    )

    if ($Directive -ne 'Redirect') {
        return $false
    }

    return (Get-RelativePathDetails -Path $SourcePattern).is_valid
}

function New-StaticRedirectMap {
    param([object[]]$RedirectRows)

    $map = @{}
    foreach ($row in $RedirectRows) {
        if (-not (Test-IsStaticRedirectSource -Directive $row.directive -SourcePattern $row.old_url_pattern)) {
            continue
        }

        $details = Get-RelativePathDetails -Path $row.old_url_pattern
        $key = $details.normalized_path.ToLowerInvariant()
        if (-not $map.ContainsKey($key)) {
            $map[$key] = New-Object System.Collections.ArrayList
        }
        [void]$map[$key].Add($row)
    }

    return $map
}

function Get-LegacyElementId {
    param([string]$NormalizedPath)

    $match = [regex]::Match($NormalizedPath, '/(?<element_id>\d+)/$')
    if ($match.Success) {
        return $match.Groups['element_id'].Value
    }

    return ''
}

function New-SitemapRegistryRow {
    param(
        [psobject]$InventoryRow,
        [hashtable]$StaticRedirectMap,
        [hashtable]$DuplicateCounts,
        [string[]]$TrustedHosts
    )

    $details = Get-PathDetails -Url $InventoryRow.old_url -TrustedHosts $TrustedHosts
    $decision = 'fix'
    $reviewStatus = 'needs_review'
    $reasonCode = 'unknown_legacy_url_type'
    $reason = 'The source URL type is not recognized by a deterministic rule.'
    $legacyElementId = ''
    $redirectCount = 0
    $legacyTargets = @()
    $duplicateCount = 0

    if ($details.is_valid) {
        $duplicateKey = $InventoryRow.old_url.Trim().ToLowerInvariant()
        if ($DuplicateCounts.ContainsKey($duplicateKey)) {
            $duplicateCount = [int]$DuplicateCounts[$duplicateKey]
        }
    }

    if (-not $details.is_valid) {
        $decision = 'remove'
        $reviewStatus = 'blocker'
        $reasonCode = $details.issue
        $reason = 'The sitemap entry cannot be safely carried into the new URL registry.'
    }
    elseif ($details.has_query_or_hash) {
        $decision = 'remove'
        $reviewStatus = 'blocker'
        $reasonCode = 'query_or_fragment_in_sitemap'
        $reason = 'A query string or fragment in an indexable source sitemap needs an explicit removal decision.'
    }
    else {
        $redirectKey = $details.normalized_path.ToLowerInvariant()
        if ($StaticRedirectMap.ContainsKey($redirectKey)) {
            $matchedRules = @($StaticRedirectMap[$redirectKey])
            $redirectCount = $matchedRules.Count
            $legacyTargets = @($matchedRules | ForEach-Object { $_.target_raw } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
            $decision = 'redirect'
            if (@($matchedRules | Where-Object { [string]::IsNullOrWhiteSpace($_.target_raw) -or $_.status -eq 'parse_error' }).Count -gt 0) {
                $reviewStatus = 'blocker'
                $reasonCode = 'legacy_redirect_without_parseable_target'
                $reason = 'A source redirect exists but its target was not extracted; no target is inferred.'
            }
            else {
                $reasonCode = 'legacy_static_redirect_requires_final_mapping'
                $reason = 'A source redirect exists. Its old target is evidence only and is not copied as a new final URL.'
            }
        }
        elseif ($InventoryRow.preliminary_type -eq 'seo_landing_candidate') {
            $decision = 'fix'
            $reasonCode = 'seo_landing_requires_value_review'
            $reason = 'An Aspro SEO landing candidate requires demand, unique-content and commercial-value review before indexing.'
        }
        elseif ($InventoryRow.preliminary_type -eq 'catalog_core') {
            $legacyElementId = Get-LegacyElementId -NormalizedPath $details.normalized_path
            if ($legacyElementId) {
                $decision = 'fix'
                $reasonCode = 'catalog_product_identity_requires_mapping'
                $reason = 'The numeric Bitrix element ID is retained as legacy identity; the new canonical URL is intentionally unset.'
            }
            else {
                $decision = 'keep'
                $reasonCode = 'catalog_section_requires_structure_review'
                $reason = 'The catalog section path is a keep candidate, pending approved information architecture and content review.'
            }
        }
    }

    if ($duplicateCount -gt 1 -and $reviewStatus -eq 'needs_review') {
        $reasonCode = "$reasonCode;duplicate_source_url"
        $reason = "$reason Duplicate sitemap entries need one approved canonical registry decision."
    }

    return [PSCustomObject][ordered]@{
        registry_kind           = 'sitemap_url'
        old_url                 = $InventoryRow.old_url
        normalized_path         = $details.normalized_path
        source                  = $InventoryRow.source
        preliminary_type        = $InventoryRow.preliminary_type
        priority                = 'unassigned'
        legacy_element_id       = $legacyElementId
        decision                = $decision
        review_status           = $reviewStatus
        reason_code             = $reasonCode
        reason                  = $reason
        duplicate_source_count = $duplicateCount
        redirect_rule_count     = $redirectCount
        legacy_target_raw       = ($legacyTargets -join ' | ')
        final_url               = ''
        owner                   = ''
        status                  = $reviewStatus
    }
}

function New-RedirectRuleRegistryRow {
    param([psobject]$RedirectRow)

    $relativeDetails = Get-RelativePathDetails -Path $RedirectRow.old_url_pattern
    $reviewStatus = 'needs_review'
    $reasonCode = 'legacy_redirect_rule_requires_final_mapping'
    $reason = 'The legacy redirect rule is source evidence only. Its target is not adopted as a final URL.'
    if ([string]::IsNullOrWhiteSpace($RedirectRow.target_raw) -or $RedirectRow.status -eq 'parse_error') {
        $reviewStatus = 'blocker'
        $reasonCode = 'legacy_redirect_rule_without_parseable_target'
        $reason = 'The legacy redirect rule has no parseable target; it requires a manual decision before cutover.'
    }

    return [PSCustomObject][ordered]@{
        registry_kind           = 'legacy_redirect_rule'
        old_url                 = $RedirectRow.old_url_pattern
        normalized_path         = $relativeDetails.normalized_path
        source                  = 'legacy-redirect-source.csv'
        preliminary_type        = 'legacy_redirect_rule'
        priority                = 'unassigned'
        legacy_element_id       = ''
        decision                = 'redirect'
        review_status           = $reviewStatus
        reason_code             = $reasonCode
        reason                  = $reason
        duplicate_source_count = 0
        redirect_rule_count     = 1
        legacy_target_raw       = $RedirectRow.target_raw
        final_url               = ''
        owner                   = ''
        status                  = $reviewStatus
    }
}

function Get-CountByValue {
    param(
        [object[]]$Rows,
        [string]$Property,
        [string[]]$Values
    )

    $counts = [ordered]@{}
    foreach ($value in $Values) {
        $counts[$value] = @($Rows | Where-Object { $_.$Property -eq $value }).Count
    }
    return $counts
}

function Invoke-SelfTest {
    $trustedHosts = @('microchips.by', 'www.microchips.by')
    $redirectRows = @(
        [PSCustomObject]@{ directive = 'Redirect'; old_url_pattern = '/catalog/batteries/100/'; target_raw = '/catalog/new-batteries/100/'; status = 'extracted' }
    )
    $redirectMap = New-StaticRedirectMap -RedirectRows $redirectRows
    $duplicates = @{ 'https://microchips.by/catalog/batteries/' = 1 }

    $product = New-SitemapRegistryRow -InventoryRow ([PSCustomObject]@{ old_url = 'https://microchips.by/catalog/batteries/123/'; source = 'sitemap.xml'; preliminary_type = 'catalog_core' }) -StaticRedirectMap $redirectMap -DuplicateCounts $duplicates -TrustedHosts $trustedHosts
    Assert-Condition -Condition ($product.decision -eq 'fix') -Message 'catalog product must be fix'
    Assert-Condition -Condition ($product.legacy_element_id -eq '123') -Message 'catalog product ID must be retained'

    $section = New-SitemapRegistryRow -InventoryRow ([PSCustomObject]@{ old_url = 'https://microchips.by/catalog/batteries/'; source = 'sitemap.xml'; preliminary_type = 'catalog_core' }) -StaticRedirectMap $redirectMap -DuplicateCounts $duplicates -TrustedHosts $trustedHosts
    Assert-Condition -Condition ($section.decision -eq 'keep') -Message 'catalog section must be keep'

    $landing = New-SitemapRegistryRow -InventoryRow ([PSCustomObject]@{ old_url = 'https://microchips.by/catalog/filter/voltage-12v/'; source = 'aspro.xml'; preliminary_type = 'seo_landing_candidate' }) -StaticRedirectMap $redirectMap -DuplicateCounts $duplicates -TrustedHosts $trustedHosts
    Assert-Condition -Condition ($landing.decision -eq 'fix') -Message 'SEO landing must be fix'

    $query = New-SitemapRegistryRow -InventoryRow ([PSCustomObject]@{ old_url = 'https://microchips.by/catalog/batteries/?sort=price'; source = 'sitemap.xml'; preliminary_type = 'catalog_core' }) -StaticRedirectMap $redirectMap -DuplicateCounts $duplicates -TrustedHosts $trustedHosts
    Assert-Condition -Condition ($query.decision -eq 'remove' -and $query.review_status -eq 'blocker') -Message 'query sitemap URL must be a removal blocker'

    $redirect = New-SitemapRegistryRow -InventoryRow ([PSCustomObject]@{ old_url = 'https://microchips.by/catalog/batteries/100/'; source = 'sitemap.xml'; preliminary_type = 'catalog_core' }) -StaticRedirectMap $redirectMap -DuplicateCounts $duplicates -TrustedHosts $trustedHosts
    Assert-Condition -Condition ($redirect.decision -eq 'redirect' -and $redirect.final_url -eq '') -Message 'legacy redirect must not create a final URL'

    Write-Output 'Self-test passed: 6 assertions.'
}

if ($RunSelfTest) {
    Invoke-SelfTest
    return
}

foreach ($path in @($InventoryPath, $RedirectSourcePath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required source file is missing: $path"
    }
}

$inventory = @(Import-Csv -LiteralPath $InventoryPath -Encoding utf8)
$redirectSource = @(Import-Csv -LiteralPath $RedirectSourcePath -Encoding utf8)
if ($inventory.Count -eq 0) {
    throw "Inventory contains no rows: $InventoryPath"
}

foreach ($requiredColumn in @('old_url', 'source', 'preliminary_type')) {
    if ($inventory[0].PSObject.Properties.Name -notcontains $requiredColumn) {
        throw "Inventory is missing required column: $requiredColumn"
    }
}
foreach ($requiredColumn in @('directive', 'old_url_pattern', 'target_raw', 'status')) {
    if ($redirectSource.Count -gt 0 -and $redirectSource[0].PSObject.Properties.Name -notcontains $requiredColumn) {
        throw "Redirect source is missing required column: $requiredColumn"
    }
}

$duplicateCounts = @{}
foreach ($row in $inventory) {
    if ([string]::IsNullOrWhiteSpace($row.old_url)) {
        continue
    }
    $key = $row.old_url.Trim().ToLowerInvariant()
    if ($duplicateCounts.ContainsKey($key)) {
        $duplicateCounts[$key] = [int]$duplicateCounts[$key] + 1
    }
    else {
        $duplicateCounts[$key] = 1
    }
}

$staticRedirectMap = New-StaticRedirectMap -RedirectRows $redirectSource
$registry = New-Object System.Collections.ArrayList
foreach ($row in $inventory) {
    [void]$registry.Add((New-SitemapRegistryRow -InventoryRow $row -StaticRedirectMap $staticRedirectMap -DuplicateCounts $duplicateCounts -TrustedHosts $AllowedHost))
}
foreach ($row in $redirectSource) {
    [void]$registry.Add((New-RedirectRuleRegistryRow -RedirectRow $row))
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$csvPath = Join-Path $OutputDir 'legacy-url-decision-registry.csv'
$summaryPath = Join-Path $OutputDir 'legacy-url-decision-summary.json'
$registry | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

$staticRuleCount = @($redirectSource | Where-Object { Test-IsStaticRedirectSource -Directive $_.directive -SourcePattern $_.old_url_pattern }).Count
$summary = [ordered]@{
    schema_version = 1
    generated_at = (Get-Date).ToString('o')
    input = [ordered]@{
        inventory_path = $InventoryPath
        inventory_rows = $inventory.Count
        redirect_source_path = $RedirectSourcePath
        redirect_rule_rows = $redirectSource.Count
    }
    output = [ordered]@{
        registry_path = $csvPath
        registry_rows = $registry.Count
    }
    decisions = Get-CountByValue -Rows $registry -Property 'decision' -Values @('keep', 'fix', 'redirect', 'remove')
    review_statuses = Get-CountByValue -Rows $registry -Property 'review_status' -Values @('needs_review', 'blocker')
    registry_kinds = Get-CountByValue -Rows $registry -Property 'registry_kind' -Values @('sitemap_url', 'legacy_redirect_rule')
    evidence = [ordered]@{
        static_redirect_rules = $staticRuleCount
        regex_or_non_static_redirect_rules = $redirectSource.Count - $staticRuleCount
        sitemap_urls_with_static_redirect_evidence = @($registry | Where-Object { $_.registry_kind -eq 'sitemap_url' -and $_.redirect_rule_count -gt 0 }).Count
        duplicate_sitemap_url_groups = @($duplicateCounts.GetEnumerator() | Where-Object { $_.Value -gt 1 }).Count
        redirects_without_parseable_target = @($redirectSource | Where-Object { [string]::IsNullOrWhiteSpace($_.target_raw) -or $_.status -eq 'parse_error' }).Count
    }
    safeguards = @(
        'final_url is empty for every row; this generator never invents or copies a production redirect destination.',
        'legacy_target_raw is evidence from the old .htaccess only and must not be treated as an approved target.',
        'priority is unassigned because the source inventories do not contain verified business or traffic priority.',
        'needs_review and blocker rows require a named owner and an explicit final decision before cutover.'
    )
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding utf8

Write-Output "Created $csvPath"
Write-Output "Created $summaryPath"
Write-Output "Registry rows: $($registry.Count)"
Write-Output "Decisions: keep=$($summary.decisions.keep); fix=$($summary.decisions.fix); redirect=$($summary.decisions.redirect); remove=$($summary.decisions.remove)"
Write-Output "Review statuses: needs_review=$($summary.review_statuses.needs_review); blocker=$($summary.review_statuses.blocker)"
