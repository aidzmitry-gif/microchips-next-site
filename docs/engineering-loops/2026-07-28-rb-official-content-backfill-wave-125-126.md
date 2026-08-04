# RB official content backfill — Waves 125–126

## Result

- Wave 125 processed 46 new manufacturer/model clusters: Delta, B.B. Battery,
  CSB, Ventura, Energizer, Leoch and FIAMM.
- Applied 29 manufacturer-primary descriptions after separate staging and
  content dry-runs: Delta 9, B.B. Battery/CSB 15, and mixed manufacturers 5.
- Wave 126 processed the three newly reached Panasonic/PKCELL clusters and
  applied one exact Panasonic `ML-1220/F1AN` description. Two variant records
  remained fail-closed because the primary sources did not prove their tab or
  exact model construction.
- Increased applied RB descriptions from 420 to 450. Price, stock, warranty,
  publication and image state were not changed.
- The cumulative no-repeat hold set reached 2,448 product records; the hold
  evidence ledger contains 209 unique clusters.

## Contract defects caught before write

- Energizer `AA 2450 mAh (HR6)` did not satisfy exact name boundaries. The
  evidence manifest was narrowed to the literal `2450 mAh` model core while
  retaining HR6 only as a sourced technical fact.
- Panasonic used the unsupported `exact_model` identity scope. It was changed
  to the supported `exact` scope with an explicit `mpn`; the Laravel gate then
  accepted it.

Neither defect reached canonical product content before correction.

## Current counters

| Metric | Value |
|---|---:|
| RB site products | 7,015 |
| Applied `ru-BY` descriptions | 450 / 7,286 (6.18%) |
| Current source-backed prices | 57 |
| Verified published media products | 44 |
| Strictly complete cards | 44 / 7,286 (0.60%) |
| Cumulative reviewed hold products | 2,448 |
| Unique hold clusters | 209 |

The 1C ×2 fallback is implemented but currently has zero usable price records:
the imported 1C snapshot does not contain a verified price, currency and price
type. The 57 current prices are source-backed legacy-site prices. No value was
invented to increase coverage.

## Queue rollover

- Wave 126 reduced its newly reached research layer to three clusters and
  closed all three by either application or explicit hold.
- The Wave 127 queue contains 57 new research clusters: Robiton 46, Panasonic
  7 and PKCELL 4. It excludes all 2,448 previously reviewed hold products.
- The queue still targets 685 additional cards against the fixed 7,286
  denominator; strict completion cannot rise until exact verified images are
  published for description-complete products.

## Verification

- All Wave 125 and 126 description manifests passed Laravel staging dry-run,
  staging apply, content dry-run and content apply.
- Applied descriptions: 9 + 15 + 5 + 1; zero commercial or publication
  changes.
- Python safety suite: 11 passed.
- `seo:audit microchips-by --json`: passed with zero blocking issues.
- Docker services: healthy.

## Main artifacts

- `docs/imports/rb-research-holds-wave-126.csv`
- `docs/audits/generated/rb-known-hold-products-wave-126-cumulative.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-126-next.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-127-summary.json`

No commit or push was performed.
