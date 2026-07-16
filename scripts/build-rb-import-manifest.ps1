[CmdletBinding()]
param(
    [string]$GeneratedDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated'),
    [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = $GeneratedDir
}

$productsPath = Join-Path $GeneratedDir 'bitrix-b2b-catalog-products.csv'
$qualityPath = Join-Path $GeneratedDir 'bitrix-b2b-catalog-quality.csv'
foreach ($required in @($productsPath, $qualityPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required generated evidence is missing: $required. Run extract-bitrix-b2b-catalog-slice.ps1 first."
    }
}

# Audit-fixed focus definition (docs/audits/2026-07-14-b2b-catalog-slice.md):
# any matched source-section membership in one of the three focus path prefixes.
$focusPrefixes = @(
    'akkumulyatory/dlya_ibp',
    'istochniki-pitaniya/ibp',
    'akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya'
)

function Test-FocusPath {
    param([string]$Path)

    foreach ($prefix in $focusPrefixes) {
        if ($Path -eq $prefix -or $Path.StartsWith("$prefix/")) {
            return $true
        }
    }
    return $false
}

function Get-FocusPathFromList {
    param([string]$PipeSeparated)

    foreach ($candidate in ($PipeSeparated -split '\|')) {
        $trimmed = $candidate.Trim()
        if ($trimmed -and (Test-FocusPath -Path $trimmed)) {
            return $trimmed
        }
    }
    return ''
}

function Get-ProposedCategory {
    param([string]$FocusPath)

    if ($FocusPath -like 'akkumulyatory/dlya_ibp*') { return 'akb-dlya-ibp' }
    if ($FocusPath -like 'istochniki-pitaniya/ibp*') { return 'ibp-ustroystva' }
    if ($FocusPath -like 'akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya*') { return 'akb-rezervnoe-pitanie' }
    return 'unmapped-review'
}

# Owner-approved rule (2026-07-16): the model code inside the source name is
# the manufacturer identity CANDIDATE (brand + MPN). Candidates still require
# supplier/1C confirmation before publication.
$typePrefixPattern = '^(?:Внешний\s+батарейный\s+блок|Модуль\s+батарейный|Батарея\s+аккумуляторная|Источник\s+бесперебойного\s+питания|Аккумуляторная\s+батарея|Аккумулятор|ИБП)\s+(?:(?:для\s+)?ИБП\s+)?'
$twoWordBrandStarts = @('Hiden', 'Atlas', 'Keheng', 'General', 'Security', 'B.B.', 'Alarm')

# Match key: uppercase, Cyrillic homoglyphs mapped to Latin, separators
# dropped — used to group case/script variants and detect identity collisions.
$homoglyphs = @{
    [char]'А' = 'A'; [char]'В' = 'B'; [char]'Е' = 'E'; [char]'К' = 'K'
    [char]'М' = 'M'; [char]'Н' = 'H'; [char]'О' = 'O'; [char]'Р' = 'P'
    [char]'С' = 'C'; [char]'Т' = 'T'; [char]'У' = 'Y'; [char]'Х' = 'X'
}

function Get-IdentityMatchKey {
    param([string]$Brand, [string]$Mpn)

    $builder = [System.Text.StringBuilder]::new()
    foreach ($character in "$Brand $Mpn".ToUpperInvariant().ToCharArray()) {
        if ([char]::IsLetterOrDigit($character)) {
            if ($homoglyphs.ContainsKey($character)) {
                [void]$builder.Append($homoglyphs[$character])
            }
            else {
                [void]$builder.Append($character)
            }
        }
    }
    return $builder.ToString()
}
$specParenPattern = '(?i)(AGM|GEL|LiFePO4|Li-?ion|Li-?Pol|NiMH|NiCd|LTO|OPzV|OPzS|\d+\s*(mah|ah|а·ч|ач)|\d+(\.\d+)?\s*(v|в)\b)'

function Get-IdentityCandidate {
    param([string]$Name)

    $working = $Name.Trim()
    $working = ([regex]::Replace($working, $typePrefixPattern, '', 'IgnoreCase')).Trim()

    $notes = [System.Collections.Generic.List[string]]::new()
    $parenBrand = ''
    foreach ($match in [regex]::Matches($working, '\(([^()]*)\)')) {
        $inner = $match.Groups[1].Value.Trim()
        if (-not [regex]::IsMatch($inner, $specParenPattern)) {
            if ($inner -match '^[A-ZА-ЯЁ][A-ZА-ЯЁa-zа-яё\-]{1,14}$') {
                $parenBrand = $inner
            }
            else {
                $notes.Add($inner)
            }
        }
    }
    $working = ([regex]::Replace($working, '\([^()]*\)', ' ')).Trim()

    # A trailing "для ИБП <Brand>" names the device vendor (e.g. APC battery
    # packs) — keep it as the brand fallback before stripping the tail.
    $tailBrand = ''
    $tailMatch = [regex]::Match($working, '\s+для\s+ИБП\s+(?<vendor>[A-Za-zА-ЯЁа-яё][\w\-]*)\s*$')
    if ($tailMatch.Success) {
        $tailBrand = $tailMatch.Groups['vendor'].Value
    }
    $working = ([regex]::Replace($working, '\s+для\s+.+$', '')).Trim()
    $working = ([regex]::Replace($working, '\s{2,}', ' '))

    $tokens = @($working -split '\s+' | Where-Object { $_ })
    $brand = ''
    $modelTokens = $tokens
    $firstIsBrandLike = $tokens.Count -gt 0 -and $tokens[0] -notmatch '\d' -and
        $tokens[0].Length -ge 2 -and -not $tokens[0].EndsWith('-')
    if ($firstIsBrandLike) {
        $brandTokenCount = 1
        if ($tokens.Count -ge 2 -and $twoWordBrandStarts -contains $tokens[0] -and $tokens[1] -notmatch '\d') {
            $brandTokenCount = 2
        }
        $brand = ($tokens[0..($brandTokenCount - 1)] -join ' ')
        $modelTokens = if ($tokens.Count -gt $brandTokenCount) { $tokens[$brandTokenCount..($tokens.Count - 1)] } else { @() }
    }
    if (-not $brand -and $parenBrand) { $brand = $parenBrand }
    if (-not $brand -and $tailBrand) { $brand = $tailBrand }

    $mpn = ($modelTokens -join ' ').Trim()
    $status = if ($brand -and $mpn) {
        'auto_from_name'
    }
    elseif ($mpn) {
        'partial_no_brand'
    }
    else {
        'needs_manual_review'
    }

    return [PSCustomObject]@{
        Brand  = $brand
        Mpn    = $mpn
        Status = $status
        Notes  = ($notes -join ' | ')
    }
}

$quality = @{}
foreach ($row in (Import-Csv -LiteralPath $qualityPath)) {
    $quality[$row.legacy_element_id] = $row
}

$products = Import-Csv -LiteralPath $productsPath

$focusRows = [System.Collections.Generic.List[object]]::new()
foreach ($product in $products) {
    $primaryInFocus = Test-FocusPath -Path $product.primary_section_path
    $matchedFocusPath = Get-FocusPathFromList -PipeSeparated $product.matched_section_paths
    if (-not $primaryInFocus -and -not $matchedFocusPath) {
        continue
    }

    $focusPath = if ($primaryInFocus) { $product.primary_section_path } else { $matchedFocusPath }
    $focusReason = if ($primaryInFocus) { 'primary_path' } else { 'additional_membership' }
    $q = $quality[$product.legacy_element_id]
    $issues = if ($q) { $q.issue_codes } else { '' }
    $duplicateCount = if ($q) { [int]$q.duplicate_name_count } else { 1 }
    $hasMedia = if ($q) { $q.has_media_reference } else { '' }

    $disposition = if ($product.active -ne 'Y') {
        'exclude_inactive_candidate'
    }
    else {
        'import_candidate_pending_identity'
    }

    $identity = Get-IdentityCandidate -Name $product.name

    $focusRows.Add([PSCustomObject][ordered]@{
        legacy_element_id        = $product.legacy_element_id
        legacy_iblock_id         = $product.legacy_iblock_id
        legacy_xml_id            = $product.legacy_xml_id
        name                     = $product.name
        active                   = $product.active
        focus_reason             = $focusReason
        focus_section_path       = $focusPath
        primary_section_path     = $product.primary_section_path
        matched_section_paths    = $product.matched_section_paths
        section_membership       = $product.section_membership
        legacy_url_candidate     = $product.legacy_url_candidate
        capacity_from_name       = $product.capacity_from_name
        voltage_from_name        = $product.voltage_from_name
        technology_from_name     = $product.technology_from_name
        quality_issue_codes      = $issues
        duplicate_name_count     = $duplicateCount
        has_media_reference      = $hasMedia
        series_hint_key          = ''
        series_hint_size         = 1
        proposed_shared_category = Get-ProposedCategory -FocusPath $focusPath
        proposed_disposition     = $disposition
        brand_candidate          = $identity.Brand
        mpn_candidate_from_name  = $identity.Mpn
        identity_extraction      = $identity.Status
        identity_match_key       = if ($identity.Mpn) { Get-IdentityMatchKey -Brand $identity.Brand -Mpn $identity.Mpn } else { '' }
        identity_collision       = ''
        name_extra_notes         = $identity.Notes
        supplier_or_1c_id        = ''
        sku                      = ''
        mpn                      = ''
        approved_category        = ''
        final_disposition        = ''
        reviewer                 = ''
        review_note              = ''
        review_status            = 'needs_review'
    })
}

# Identity collisions: rows sharing one match key are either true duplicates
# or product variants (e.g. с/без электролита, AGM vs GEL) — reviewers must
# split or merge them explicitly before import.
$collisionGroups = @{}
foreach ($row in $focusRows) {
    if ($row.identity_match_key) {
        if (-not $collisionGroups.ContainsKey($row.identity_match_key)) {
            $collisionGroups[$row.identity_match_key] = [System.Collections.Generic.List[object]]::new()
        }
        $collisionGroups[$row.identity_match_key].Add($row)
    }
}
$collisionGroupCount = 0
foreach ($entry in $collisionGroups.GetEnumerator()) {
    if ($entry.Value.Count -gt 1) {
        $collisionGroupCount++
        foreach ($row in $entry.Value) {
            $row.identity_collision = "shared_key_x$($entry.Value.Count)"
        }
    }
}

# Series hints: names that only differ in digit runs are likely one model range.
$seriesGroups = @{}
foreach ($row in $focusRows) {
    $key = ([regex]::Replace($row.name, '\d+([\.,]\d+)?', '#')).Trim().ToLowerInvariant()
    if (-not $seriesGroups.ContainsKey($key)) {
        $seriesGroups[$key] = [System.Collections.Generic.List[object]]::new()
    }
    $seriesGroups[$key].Add($row)
}
$seriesHintGroups = 0
foreach ($entry in $seriesGroups.GetEnumerator()) {
    if ($entry.Value.Count -gt 1) {
        $seriesHintGroups++
        foreach ($row in $entry.Value) {
            $row.series_hint_key = $entry.Key
            $row.series_hint_size = $entry.Value.Count
        }
    }
}

# Integrity: totals must match the audit scope correction exactly.
$total = $focusRows.Count
$primaryCount = @($focusRows | Where-Object focus_reason -eq 'primary_path').Count
$additionalCount = @($focusRows | Where-Object focus_reason -eq 'additional_membership').Count
$expected = @{ total = 1569; primary = 1445; additional = 124 }
if ($total -ne $expected.total -or $primaryCount -ne $expected.primary -or $additionalCount -ne $expected.additional) {
    throw ("Focus counts diverge from the audited scope (expected {0}/{1}/{2}, got {3}/{4}/{5}). " -f
        $expected.total, $expected.primary, $expected.additional, $total, $primaryCount, $additionalCount) +
        'Re-check the audit scope correction before publishing a manifest.'
}

$manifestPath = Join-Path $OutputDir 'rb-import-manifest-draft.csv'
@($focusRows | Sort-Object proposed_shared_category, name) |
    Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8

$summary = [PSCustomObject][ordered]@{
    generated_at_utc            = [DateTime]::UtcNow.ToString('o')
    source_products_csv         = $productsPath
    focus_definition            = 'any matched source-section membership in the three UPS/reserve focus prefixes'
    focus_total                 = $total
    focus_primary_path          = $primaryCount
    focus_additional_membership = $additionalCount
    inactive_excluded_candidates = @($focusRows | Where-Object proposed_disposition -eq 'exclude_inactive_candidate').Count
    without_media_reference     = @($focusRows | Where-Object has_media_reference -eq 'false').Count
    series_hint_groups          = $seriesHintGroups
    rows_in_series_hints        = @($focusRows | Where-Object { $_.series_hint_size -gt 1 }).Count
    identity_auto_from_name     = @($focusRows | Where-Object identity_extraction -eq 'auto_from_name').Count
    identity_partial_no_brand   = @($focusRows | Where-Object identity_extraction -eq 'partial_no_brand').Count
    identity_needs_manual       = @($focusRows | Where-Object identity_extraction -eq 'needs_manual_review').Count
    distinct_brand_candidates   = @($focusRows | Where-Object brand_candidate | Select-Object -ExpandProperty brand_candidate -Unique).Count
    identity_collision_groups   = $collisionGroupCount
    identity_collision_rows     = @($focusRows | Where-Object identity_collision).Count
    by_proposed_category        = [PSCustomObject]([ordered]@{
        'akb-dlya-ibp'          = @($focusRows | Where-Object proposed_shared_category -eq 'akb-dlya-ibp').Count
        'ibp-ustroystva'        = @($focusRows | Where-Object proposed_shared_category -eq 'ibp-ustroystva').Count
        'akb-rezervnoe-pitanie' = @($focusRows | Where-Object proposed_shared_category -eq 'akb-rezervnoe-pitanie').Count
        'unmapped-review'       = @($focusRows | Where-Object proposed_shared_category -eq 'unmapped-review').Count
    })
    identity_columns_filled     = 0
    review_status               = 'all_rows_need_review'
    publication_gate            = 'blocked_until_supplier_or_1c_identity_filled_and_approved'
}
$summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'rb-import-manifest-summary.json') -Encoding utf8

Write-Output "Manifest draft: $manifestPath"
Write-Output ("Focus rows: {0} (primary {1}, additional {2}); series hint groups: {3}" -f $total, $primaryCount, $additionalCount, $seriesHintGroups)
