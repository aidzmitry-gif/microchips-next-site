# RB official content backfill — Waves 122–124

## Result

- Processed three consecutive no-repeat catalogue layers using official
  manufacturer sources and a cumulative hold registry.
- Applied 96 source-backed `ru-BY` descriptions: 46 in Wave 122, 39 in Wave
  123 and 11 in Wave 124.
- Increased applied RB descriptions from 324 to 420 without changing price,
  stock, warranty, publication or other commercial fields.
- Expanded the cumulative skipped/hold set to 1,877 product records and the
  evidence ledger to 189 unique clusters. Reviewed rows are not sent back into
  the next research batch.
- Corrected the `Tekcell СR17450-3v` hold key so the Cyrillic first character
  matches the deterministic cluster ID. The rebuilt Wave 123 batch then had
  zero unresolved research clusters.
- Corrected the out-of-scope detector: words describing an installation part
  no longer exclude a battery or cell merely because its name also contains a
  connector or wire reference.

All manifests were applied through separate Laravel staging dry-run, staging
apply, content dry-run and content apply gates. No products were published.

## Current counters

| Metric | Value |
|---|---:|
| RB site products | 7,015 |
| Applied `ru-BY` descriptions | 420 |
| Verified published media products | 44 |
| Strictly complete cards | 44 / 7,286 (0.60%) |
| Cumulative reviewed hold products | 1,877 |
| Unique hold clusters | 189 |

The description coverage is `420 / 7,286 = 5.76%`. It is not reported as
strict card completeness because every card still requires an exact,
rights-safe, independently verified published image. Strict completeness
therefore remains 0.60%.

## No-repeat rollover

- Wave 123 finished with zero unresolved clusters in its processed queue.
- Wave 124 reduced 685 queue rows to 18 new model clusters. Eleven product
  records passed official-source validation; unresolved identities were moved
  to hold.
- The Wave 125 queue contains 46 new research clusters after excluding all
  1,877 cumulative hold products. Its largest groups are Delta, B.B. Battery,
  CSB, Ventura, Energizer and Leoch.

## Media gate

The exact-name legacy-media candidate builder was run for all Wave 121 and 122
description manifests. It emitted zero candidates because none had both a
unique exact legacy match and complete media references. No approximate image
was imported and no strict-completeness point was claimed.

## Verification

- Python safety tests: 11 passed.
- Laravel content gates for Wave 124: 8 + 1 + 2 records validated and applied;
  zero publication and commercial-data changes.
- `seo:audit microchips-by --json`: 119 URLs, zero blocking issues.
- Docker backend, frontend, nginx, PostgreSQL and Redis: healthy.
- Wave 125 queue build: 685 records, fixed denominator 7,286, no remaining
  target-gap after queue construction.

## Main artifacts

- `docs/imports/rb-research-holds-wave-124.csv`
- `docs/audits/generated/rb-known-hold-products-wave-124-cumulative.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-124-next.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-125-summary.json`
- `scripts/build-exact-legacy-media-candidates.py`
- `scripts/build-rb-batch-catalog-triage.py`
- `scripts/merge-rb-research-holds.py`

No commit or push was performed.
