param(
  [string]$Candidates = "docs/audits/generated/wave201-industrial-batch-candidates.csv",
  [string]$OutDir = "docs/audits/generated",
  [string]$SiteKey = "microchips-by"
)

$ErrorActionPreference = 'Stop'

$batches = @(
  'zebra_legacy_mobile_computers',
  'honeywell_mobile_computers',
  'datalogic_data_capture',
  'intermec_mobile_computers'
)
$rows = @(Import-Csv -LiteralPath $Candidates | Where-Object { $_.batch -in $batches })
if ($rows.Count -ne 237) { throw "Expected 237 Wave202 rows, got $($rows.Count)" }
$candidateIds = @($rows | ForEach-Object { $_.product_external_id })
if (@($candidateIds | Sort-Object -Unique).Count -ne 237) { throw 'Wave202 product_external_id values are not unique' }

# The research partitions are authoritative for no-repeat handling.  Derive the
# set instead of maintaining another manual list that can drift.
$zebraEvidence = @(Import-Csv -LiteralPath (Join-Path $OutDir 'wave202-zebra-legacy-mobile-computers-evidence.csv'))
$honeywellEvidence = @(Import-Csv -LiteralPath (Join-Path $OutDir 'rb-wave202-honeywell-evidence.csv'))
$oemEvidence = @(Import-Csv -LiteralPath (Join-Path $OutDir 'wave202-oem-replacement-evidence.csv'))
$previouslyProcessedIds = @(
  @($zebraEvidence | Where-Object { $_.repeat_handling -eq 'previously_processed' } | ForEach-Object { $_.product_external_id })
  @($honeywellEvidence | Where-Object { $_.classification -eq 'previously_processed' } | ForEach-Object { $_.product_external_id })
  @($oemEvidence | Where-Object { $_.partition -eq 'previously_processed' } | ForEach-Object { $_.product_external_id })
) | Sort-Object -Unique
if ($previouslyProcessedIds.Count -ne 9) { throw "Expected 9 previously processed Wave202 rows, got $($previouslyProcessedIds.Count)" }

# Query in bounded batches.  The command is read-only and deliberately avoids
# loading all candidate IDs into a single Tinker expression on Windows.
$dbRows = @()
for ($offset = 0; $offset -lt $rows.Count; $offset += 25) {
  $slice = @($rows | Select-Object -Skip $offset -First 25)
  $ids = @($slice | ForEach-Object { "'$($_.product_external_id.Replace("'", "''"))'" }) -join ','
  $escapedSiteKey = $SiteKey.Replace("'", "''")
  $php = @"
`$siteId=app('db')->table('sites')->where('key','$escapedSiteKey')->value('id');
if(!`$siteId){throw new RuntimeException('Site not found');}
`$ids=[$ids];
`$q=app('db')->table('products as p')->whereIn('p.external_id',`$ids)
 ->select('p.id','p.external_id','p.status')
 ->selectRaw("(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_product_id",[`$siteId])
 ->selectRaw("(select sp.is_published from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) site_is_published",[`$siteId])
 ->selectRaw("(select sp.price from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) current_price",[`$siteId])
 ->selectRaw("(select sp.availability from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) availability",[`$siteId])
 ->selectRaw("(select pe.currency from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true order by pe.observed_at desc limit 1) currency",[`$siteId])
 ->selectRaw("(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1)) price_evidence_count",[`$siteId])
 ->selectRaw("(select count(*) from site_product_price_evidences pe where pe.site_product_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) and pe.is_current=true) current_price_evidence_count",[`$siteId])
 ->selectRaw("(select count(*) from product_media pm where pm.product_id=p.id) media_count")
 ->selectRaw("(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status='verified') verified_published_media_count")
 ->selectRaw("(select count(*) from product_description_drafts pd where pd.product_id=p.id and pd.status in ('applied','legacy_preview_applied')) applied_source_draft_count")
 ->selectRaw("(select cast(seo.schema as text) from site_seos seo where seo.site_id=? and seo.resource_type='product' and seo.resource_id=(select sp.id from site_products sp where sp.product_id=p.id and sp.site_id=? limit 1) limit 1) schema_json",[`$siteId,`$siteId]);
echo json_encode(`$q->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
"@ -replace "`r?`n", ''
  $encodedPhp = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($php))
  $tinkerExpression = "eval(base64_decode('$encodedPhp'));"
  $payload = [string]::Join("`n", @(& docker compose exec -T backend php artisan tinker ("--execute=$tinkerExpression")))
  if (-not $payload.TrimStart().StartsWith('[')) { throw "Unexpected Tinker output for batch ${offset}: $payload`nPHP: $php" }
  $parsedBatch = $payload | ConvertFrom-Json
  $batchRows = @()
  foreach ($parsedItem in $parsedBatch) { $batchRows += $parsedItem }
  $returnedIds = @($batchRows | ForEach-Object { $_.external_id })
  $uniqueReturnedCount = @($returnedIds | Sort-Object -Unique).Count
  if ($uniqueReturnedCount -ne $batchRows.Count) { throw "Duplicate DB rows in batch ${offset}: rows=$($batchRows.Count), unique=$uniqueReturnedCount, ids=$($returnedIds -join ',')" }
  $dbRows += $batchRows
}

$byId = @{}
foreach ($item in $dbRows) { $byId[$item.external_id] = $item }

$result = @(
  foreach ($row in $rows) {
    $name = $row.name
    # Only explicit part-number-like tokens are used for strict grouping.  A
    # shared device model alone is compatibility context, not product identity.
    $tokenMatch = [regex]::Match($name, '(?i)\b(?:BAT|BTRY|CT|EDA|CS|P\d|\d{2}ACC)[A-Z0-9-]*\b')
    $voltageMatch = [regex]::Match($name, '(?i)(\d+(?:[.,]\s*\d+)?)\s*V\b')
    $capacityMatch = [regex]::Match($name, '(?i)(\d+)\s*mAh\b')
    $db = $byId[$row.product_external_id]
    $hasDbProduct = $null -ne $db
    $hasSiteProduct = $hasDbProduct -and $null -ne $db.site_product_id
    $priceEvidenceCount = if ($hasDbProduct) { [int]$db.price_evidence_count } else { 0 }
    $currentPriceEvidenceCount = if ($hasDbProduct) { [int]$db.current_price_evidence_count } else { 0 }
    $mediaCount = if ($hasDbProduct) { [int]$db.media_count } else { 0 }
    $verifiedPublishedMediaCount = if ($hasDbProduct) { [int]$db.verified_published_media_count } else { 0 }
    $appliedSourceDraftCount = if ($hasDbProduct) { [int]$db.applied_source_draft_count } else { 0 }
    $schemaJson = if ($hasDbProduct -and $null -ne $db.schema_json) { [string]$db.schema_json } else { '' }
    $hasOfferSchema = $schemaJson -match '(?i)"offers?"|"@type"\s*:\s*"Offer"'
    $commercialGuard = 'no_unsupported_commercial_claim'
    if ($hasSiteProduct -and $db.availability -eq 'in_stock') {
      $commercialGuard = 'BLOCK_in_stock_without_stock_evidence'
    } elseif ($hasSiteProduct -and $null -ne $db.current_price -and $currentPriceEvidenceCount -eq 0) {
      $commercialGuard = 'BLOCK_price_without_current_evidence'
    } elseif ($hasOfferSchema -and $currentPriceEvidenceCount -eq 0) {
      $commercialGuard = 'BLOCK_offer_without_current_price_evidence'
    }

    [pscustomobject]@{
      batch = $row.batch
      product_external_id = $row.product_external_id
      legacy_name = $name
      model_token = if ($tokenMatch.Success) { $tokenMatch.Value.ToUpperInvariant() } else { '' }
      voltage_token = if ($voltageMatch.Success) { $voltageMatch.Groups[1].Value.Replace(' ','').Replace(',','.') } else { '' }
      capacity_token_mah = if ($capacityMatch.Success) { $capacityMatch.Groups[1].Value } else { '' }
      current_product = $hasDbProduct.ToString().ToLowerInvariant()
      current_product_status = if ($hasDbProduct) { $db.status } else { '' }
      rb_site_product = $hasSiteProduct.ToString().ToLowerInvariant()
      rb_is_published = if ($hasSiteProduct) { ([bool]$db.site_is_published).ToString().ToLowerInvariant() } else { '' }
      current_price = if ($hasSiteProduct) { $db.current_price } else { $null }
      currency = if ($hasSiteProduct) { $db.currency } else { $null }
      availability = if ($hasSiteProduct) { $db.availability } else { $null }
      price_evidence_count = $priceEvidenceCount
      current_price_evidence_count = $currentPriceEvidenceCount
      media_count = $mediaCount
      verified_published_media_count = $verifiedPublishedMediaCount
      applied_source_draft_count = $appliedSourceDraftCount
      offer_schema_present = $hasOfferSchema.ToString().ToLowerInvariant()
      previously_processed = ($row.product_external_id -in $previouslyProcessedIds).ToString().ToLowerInvariant()
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
    Where-Object { $_.model_token -and $_.voltage_token -and $_.capacity_token_mah } |
    Group-Object { "$($_.model_token)|$($_.voltage_token)|$($_.capacity_token_mah)" } |
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
$csvPath = Join-Path $OutDir 'rb-wave202-commercial-duplicate-guard.csv'
$result | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding utf8

$summary = [ordered]@{
  wave = 'wave202'
  site_key = $SiteKey
  candidate_records = $result.Count
  current_db_records = @($result | Where-Object { $_.current_product -eq 'true' }).Count
  current_db_missing_records = @($result | Where-Object { $_.current_product -eq 'false' }).Count
  rb_site_product_records = @($result | Where-Object { $_.rb_site_product -eq 'true' }).Count
  batch_counts = [ordered]@{}
  current_price_records = @($result | Where-Object { $null -ne $_.current_price -and $_.current_price -ne '' }).Count
  currency_records = @($result | Where-Object { $_.currency }).Count
  in_stock_records = @($result | Where-Object { $_.availability -eq 'in_stock' }).Count
  offer_schema_records = @($result | Where-Object { $_.offer_schema_present -eq 'true' }).Count
  unsupported_commercial_claims = @($result | Where-Object { $_.offer_claim_guard -ne 'no_unsupported_commercial_claim' }).Count
  price_evidence_records = @($result | Measure-Object -Property price_evidence_count -Sum).Sum
  current_price_evidence_records = @($result | Measure-Object -Property current_price_evidence_count -Sum).Sum
  media_records = @($result | Measure-Object -Property media_count -Sum).Sum
  verified_published_media_records = @($result | Measure-Object -Property verified_published_media_count -Sum).Sum
  applied_source_draft_records = @($result | Measure-Object -Property applied_source_draft_count -Sum).Sum
  strict_duplicate_groups = $groups.Count
  strict_duplicate_candidates = @($result | Where-Object { $_.strict_duplicate_candidate -eq 'true' }).Count
  previously_processed_records = @($result | Where-Object { $_.previously_processed -eq 'true' }).Count
  safe_to_apply = $false
  automatic_database_mutations = 0
}
foreach ($batch in $batches) { $summary.batch_counts[$batch] = @($result | Where-Object { $_.batch -eq $batch }).Count }

$summaryPath = Join-Path $OutDir 'rb-wave202-commercial-duplicate-guard-summary.json'
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $summaryPath -Encoding utf8
$summary | ConvertTo-Json -Depth 4
