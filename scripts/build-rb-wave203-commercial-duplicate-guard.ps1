param(
  [string]$Candidates = "docs/audits/generated/wave203-industrial-unassigned-preparation.csv",
  [string]$PropertyValues = "docs/audits/generated/bitrix-b2b-catalog-property-values.csv",
  [string]$OutDir = "docs/audits/generated",
  [string]$SiteKey = "microchips-by",
  [int]$TinkerBatchSize = 20
)

$ErrorActionPreference = 'Stop'

$rows = @(
  Import-Csv -LiteralPath $Candidates |
    Where-Object { $_.recommended_wave -eq 'wave203' -and $_.repeat_handling -eq 'new' }
)
if ($rows.Count -ne 143) { throw "Expected 143 Wave203 rows, got $($rows.Count)" }
$candidateIds = @($rows | ForEach-Object { $_.product_external_id })
if (@($candidateIds | Sort-Object -Unique).Count -ne 143) { throw 'Wave203 product_external_id values are not unique' }
if ($TinkerBatchSize -lt 1 -or $TinkerBatchSize -gt 25) { throw 'TinkerBatchSize must be between 1 and 25' }

# Reconcile the three read-only evidence partitions before querying the DB.
$evidenceFiles = @(
  (Join-Path $OutDir 'wave203-capture-evidence.csv'),
  (Join-Path $OutDir 'wave203-pos-evidence.csv'),
  (Join-Path $OutDir 'wave203-remaining-evidence.csv')
)
$evidenceMap = @{}
foreach ($file in $evidenceFiles) {
  foreach ($evidence in @(Import-Csv -LiteralPath $file)) {
    $id = $evidence.product_external_id
    if ($evidenceMap.ContainsKey($id)) { throw "Wave203 evidence overlap for $id" }
    $evidenceMap[$id] = $evidence
  }
}
if ($evidenceMap.Count -ne 143) { throw "Expected 143 union evidence rows, got $($evidenceMap.Count)" }
$uncovered = @($candidateIds | Where-Object { -not $evidenceMap.ContainsKey($_) })
if ($uncovered.Count -gt 0) { throw "Wave203 union evidence misses: $($uncovered -join ',')" }

# Pin legacy commercial/specification source values without treating them as
# current claims.  They are used for exact duplicate keys and transfer guards.
$legacyIds = @{}
foreach ($id in $candidateIds) { $legacyIds[$id.Replace('bitrix:', '')] = $id }
$propertyMap = @{}
$wantedCodes = @('MINIMUM_PRICE', 'MAXIMUM_PRICE', 'IN_STOCK', 'VOLTAGE', 'EMKOST_MAH')
foreach ($property in @(Import-Csv -LiteralPath $PropertyValues)) {
  if (-not $legacyIds.ContainsKey($property.legacy_element_id)) { continue }
  if ($property.property_code -notin $wantedCodes) { continue }
  $externalId = $legacyIds[$property.legacy_element_id]
  if (-not $propertyMap.ContainsKey($externalId)) { $propertyMap[$externalId] = @{} }
  $propertyMap[$externalId][$property.property_code] = $property.source_value_display
}

function Get-NumericToken([string]$Value) {
  if (-not $Value) { return '' }
  $match = [regex]::Match($Value, '(?i)(\d+(?:[.,]\s*\d+)?)')
  if (-not $match.Success) { return '' }
  return $match.Groups[1].Value.Replace(' ', '').Replace(',', '.')
}

function Get-StrictIdentityToken([string]$Name, [string]$ModelTokens) {
  $candidates = @()
  foreach ($match in [regex]::Matches($Name, '\(([^)]*)\)')) {
    $candidates += @($match.Groups[1].Value -split '[,;\s]+')
  }
  $candidates += @($ModelTokens -split '\|')
  foreach ($raw in $candidates) {
    $token = $raw.Trim().Trim('(', ')', ',', ';').ToUpperInvariant()
    if (-not $token) { continue }
    if ($token -match '(?i)^\d+(?:[.,]\d+)?(?:MAH|AH|V)$') { continue }
    if ($token -match '(?i)^\d+S\d+P$') { continue }
    if ($token -notmatch '[A-Z]') { continue }
    if ($token -notmatch '\d') { continue }
    if ($token.Length -lt 4) { continue }
    return ($token -replace '\s+', '')
  }
  return ''
}

# Query only read-only projections, in bounded batches safe for Windows Tinker.
$dbRows = @()
for ($offset = 0; $offset -lt $rows.Count; $offset += $TinkerBatchSize) {
  $slice = @($rows | Select-Object -Skip $offset -First $TinkerBatchSize)
  $ids = @($slice | ForEach-Object { "'$($_.product_external_id.Replace("'", "''"))'" }) -join ','
  $escapedSiteKey = $SiteKey.Replace("'", "''")
  $php = @"
`$siteId=app('db')->table('sites')->where('key','$escapedSiteKey')->value('id');
if(!`$siteId){throw new RuntimeException('Site not found');}
`$ids=[$ids];
`$q=app('db')->table('products as p')->whereIn('p.external_id',`$ids)
 ->select('p.id','p.external_id','p.name','p.status','p.manufacturer','p.mpn')
 ->selectRaw("(select count(*) from site_products sp where sp.product_id=p.id and sp.site_id=?) site_product_count",[`$siteId])
 ->selectRaw("(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_product_id",[`$siteId])
 ->selectRaw("(select sp.is_published from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_is_published",[`$siteId])
 ->selectRaw("(select sp.price from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) current_price",[`$siteId])
 ->selectRaw("(select sp.availability from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) availability",[`$siteId])
 ->selectRaw("(select pe.currency from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true order by pe.observed_at desc limit 1) currency",[`$siteId])
 ->selectRaw("(select pe.calculated_price from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true order by pe.observed_at desc limit 1) evidence_calculated_price",[`$siteId])
 ->selectRaw("(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) price_evidence_count",[`$siteId])
 ->selectRaw("(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true) current_price_evidence_count",[`$siteId])
 ->selectRaw("(select count(*) from product_media pm where pm.product_id=p.id) media_count")
 ->selectRaw("(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true) published_media_count")
 ->selectRaw("(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status='verified') verified_published_media_count")
 ->selectRaw("(select count(*) from product_description_drafts pd where pd.product_id=p.id) description_draft_count")
 ->selectRaw("(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.manufacturer_primary=true) manufacturer_primary_draft_count")
 ->selectRaw("(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.status in ('applied','legacy_preview_applied')) applied_source_draft_count")
 ->selectRaw("(select cast(seo.schema as text) from site_seos seo where seo.site_id=? and seo.resource_type='product' and seo.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) limit 1) schema_json",[`$siteId,`$siteId]);
echo json_encode(`$q->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
"@ -replace "`r?`n", ''
  $encodedPhp = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($php))
  $tinkerExpression = "eval(base64_decode('$encodedPhp'));"
  $payload = ''
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    $payload = [string]::Join("`n", @(& docker compose exec -T backend php artisan tinker ("--execute=$tinkerExpression")))
    if ($payload.TrimStart().StartsWith('[')) { break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $payload.TrimStart().StartsWith('[')) { throw "Unexpected Tinker output for batch ${offset}: $payload" }
  $parsedBatch = $payload | ConvertFrom-Json
  $batchRows = @()
  foreach ($parsedItem in $parsedBatch) { $batchRows += $parsedItem }
  $returnedIds = @($batchRows | ForEach-Object { $_.external_id })
  if (@($returnedIds | Sort-Object -Unique).Count -ne $batchRows.Count) {
    throw "Duplicate DB rows in batch ${offset}: rows=$($batchRows.Count), unique=$(@($returnedIds | Sort-Object -Unique).Count), ids=$($returnedIds -join ',')"
  }
  $dbRows += $batchRows
}

$byId = @{}
foreach ($item in $dbRows) { $byId[$item.external_id] = $item }

$result = @(
  foreach ($row in $rows) {
    $externalId = $row.product_external_id
    $db = $byId[$externalId]
    $hasDbProduct = $null -ne $db
    $siteProductCount = if ($hasDbProduct) { [int]$db.site_product_count } else { 0 }
    $hasSiteProduct = $siteProductCount -gt 0
    $legacy = if ($propertyMap.ContainsKey($externalId)) { $propertyMap[$externalId] } else { @{} }
    $legacyMinPrice = $legacy['MINIMUM_PRICE']
    $legacyMaxPrice = $legacy['MAXIMUM_PRICE']
    $legacyInStock = $legacy['IN_STOCK']
    $voltage = Get-NumericToken $legacy['VOLTAGE']
    $capacity = Get-NumericToken $legacy['EMKOST_MAH']
    $identityToken = Get-StrictIdentityToken $row.name $row.model_tokens_unverified
    $priceEvidenceCount = if ($hasDbProduct) { [int]$db.price_evidence_count } else { 0 }
    $currentPriceEvidenceCount = if ($hasDbProduct) { [int]$db.current_price_evidence_count } else { 0 }
    $schemaJson = if ($hasDbProduct -and $null -ne $db.schema_json) { [string]$db.schema_json } else { '' }
    $hasOfferSchema = $schemaJson -match '(?i)"offers?"|"@type"\s*:\s*"Offer"'
    $guards = @()
    if ($siteProductCount -gt 1) { $guards += 'BLOCK_multiple_site_products' }
    if ($hasSiteProduct -and $db.availability -eq 'in_stock') { $guards += 'BLOCK_in_stock_without_stock_evidence' }
    if ($hasSiteProduct -and $null -ne $db.current_price -and $currentPriceEvidenceCount -eq 0) { $guards += 'BLOCK_price_without_current_evidence' }
    if ($hasSiteProduct -and $null -ne $db.current_price -and $currentPriceEvidenceCount -gt 0 -and [decimal]$db.current_price -ne [decimal]$db.evidence_calculated_price) { $guards += 'BLOCK_price_evidence_mismatch' }
    if ($hasOfferSchema -and ($currentPriceEvidenceCount -eq 0 -or $null -eq $db.current_price)) { $guards += 'BLOCK_offer_without_current_price_evidence' }
    if ($hasOfferSchema -and $db.availability -eq 'in_stock') { $guards += 'BLOCK_offer_in_stock_without_stock_evidence' }
    $commercialGuard = if ($guards.Count -eq 0) { 'no_unsupported_commercial_claim' } else { $guards -join '|' }
    $evidence = $evidenceMap[$externalId]

    [pscustomobject]@{
      batch = 'wave203_mobile_computers_pos_data_capture'
      product_external_id = $externalId
      legacy_name = $row.name
      evidence_partition = $evidence.partition
      strict_identity_token = $identityToken
      voltage_v = $voltage
      capacity_mah = $capacity
      legacy_minimum_price = $legacyMinPrice
      legacy_maximum_price = $legacyMaxPrice
      legacy_in_stock = $legacyInStock
      current_product = $hasDbProduct.ToString().ToLowerInvariant()
      current_name = if ($hasDbProduct) { $db.name } else { '' }
      current_product_status = if ($hasDbProduct) { $db.status } else { '' }
      current_manufacturer = if ($hasDbProduct) { $db.manufacturer } else { '' }
      current_mpn = if ($hasDbProduct) { $db.mpn } else { '' }
      rb_site_product_count = $siteProductCount
      rb_site_product = $hasSiteProduct.ToString().ToLowerInvariant()
      rb_is_published = if ($hasSiteProduct) { ([bool]$db.site_is_published).ToString().ToLowerInvariant() } else { '' }
      current_price = if ($hasSiteProduct) { $db.current_price } else { $null }
      currency = if ($hasSiteProduct) { $db.currency } else { $null }
      availability = if ($hasSiteProduct) { $db.availability } else { $null }
      price_evidence_count = $priceEvidenceCount
      current_price_evidence_count = $currentPriceEvidenceCount
      evidence_calculated_price = if ($hasSiteProduct) { $db.evidence_calculated_price } else { $null }
      media_count = if ($hasDbProduct) { [int]$db.media_count } else { 0 }
      published_media_count = if ($hasDbProduct) { [int]$db.published_media_count } else { 0 }
      verified_published_media_count = if ($hasDbProduct) { [int]$db.verified_published_media_count } else { 0 }
      description_draft_count = if ($hasDbProduct) { [int]$db.description_draft_count } else { 0 }
      manufacturer_primary_draft_count = if ($hasDbProduct) { [int]$db.manufacturer_primary_draft_count } else { 0 }
      applied_source_draft_count = if ($hasDbProduct) { [int]$db.applied_source_draft_count } else { 0 }
      offer_schema_present = $hasOfferSchema.ToString().ToLowerInvariant()
      strict_duplicate_group_key = ''
      strict_duplicate_group_size = 0
      strict_duplicate_candidate = 'false'
      offer_claim_guard = $commercialGuard
      safe_to_apply = 'false'
    }
  }
)

$groups = @(
  $result |
    Where-Object { $_.strict_identity_token -and $_.voltage_v -and $_.capacity_mah } |
    Group-Object { "$($_.strict_identity_token)|$($_.voltage_v)|$($_.capacity_mah)" } |
    Where-Object { $_.Count -gt 1 }
)
foreach ($group in $groups) {
  foreach ($item in $group.Group) {
    $item.strict_duplicate_group_key = $group.Name
    $item.strict_duplicate_group_size = $group.Count
    $item.strict_duplicate_candidate = 'true'
  }
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$csvPath = Join-Path $OutDir 'rb-wave203-commercial-duplicate-guard.csv'
$result | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

$summary = [ordered]@{
  wave = 'wave203'
  site_key = $SiteKey
  candidate_records = $result.Count
  current_db_records = @($result | Where-Object { $_.current_product -eq 'true' }).Count
  current_db_missing_records = @($result | Where-Object { $_.current_product -eq 'false' }).Count
  current_db_missing_external_ids = @($result | Where-Object { $_.current_product -eq 'false' } | ForEach-Object { $_.product_external_id })
  rb_site_product_records = @($result | Where-Object { $_.rb_site_product -eq 'true' }).Count
  current_price_records = @($result | Where-Object { $null -ne $_.current_price -and $_.current_price -ne '' }).Count
  currency_records = @($result | Where-Object { $_.currency }).Count
  in_stock_records = @($result | Where-Object { $_.availability -eq 'in_stock' }).Count
  offer_schema_records = @($result | Where-Object { $_.offer_schema_present -eq 'true' }).Count
  unsupported_commercial_claims = @($result | Where-Object { $_.offer_claim_guard -ne 'no_unsupported_commercial_claim' }).Count
  unsupported_commercial_external_ids = @($result | Where-Object { $_.offer_claim_guard -ne 'no_unsupported_commercial_claim' } | ForEach-Object { $_.product_external_id })
  legacy_price_claim_records = @($result | Where-Object { $_.legacy_minimum_price -or $_.legacy_maximum_price }).Count
  legacy_in_stock_claim_records = @($result | Where-Object { $_.legacy_in_stock -match '^(?i:Y|YES|TRUE|1)$' }).Count
  price_evidence_records = @($result | Measure-Object -Property price_evidence_count -Sum).Sum
  current_price_evidence_records = @($result | Measure-Object -Property current_price_evidence_count -Sum).Sum
  media_records = @($result | Measure-Object -Property media_count -Sum).Sum
  published_media_records = @($result | Measure-Object -Property published_media_count -Sum).Sum
  verified_published_media_records = @($result | Measure-Object -Property verified_published_media_count -Sum).Sum
  description_draft_records = @($result | Measure-Object -Property description_draft_count -Sum).Sum
  manufacturer_primary_draft_records = @($result | Measure-Object -Property manufacturer_primary_draft_count -Sum).Sum
  applied_source_draft_records = @($result | Measure-Object -Property applied_source_draft_count -Sum).Sum
  strict_duplicate_groups = $groups.Count
  strict_duplicate_candidates = @($result | Where-Object { $_.strict_duplicate_candidate -eq 'true' }).Count
  strict_duplicate_group_keys = @($groups | ForEach-Object { $_.Name })
  tinker_batch_size = $TinkerBatchSize
  tinker_batches = [math]::Ceiling($rows.Count / $TinkerBatchSize)
  evidence_union_records = $evidenceMap.Count
  candidate_sha256 = (Get-FileHash -LiteralPath $Candidates -Algorithm SHA256).Hash.ToLowerInvariant()
  property_values_sha256 = (Get-FileHash -LiteralPath $PropertyValues -Algorithm SHA256).Hash.ToLowerInvariant()
  output_sha256 = (Get-FileHash -LiteralPath $csvPath -Algorithm SHA256).Hash.ToLowerInvariant()
  safe_to_apply = $false
  automatic_database_mutations = 0
}
$summaryPath = Join-Path $OutDir 'rb-wave203-commercial-duplicate-guard-summary.json'
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding utf8
$summary | ConvertTo-Json -Depth 5
