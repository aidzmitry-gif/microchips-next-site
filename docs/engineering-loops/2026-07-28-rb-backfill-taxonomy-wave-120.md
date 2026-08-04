# RB backfill and uncategorized cleanup — Wave 120

## Result

- Added an auditable prior-decision registry for all 62 previously researched
  model clusters. A hold keeps the product and its readiness debt, but stops
  repeated official-source searches until the stated retry condition changes.
- Extended the enrichment queue with a fail-closed `--skip-file`. Skipped
  products remain in the fixed baseline and completeness calculation; only
  queue selection skips them and backfills later products.
- Classified all 276 RB site products that had no category: 2 high-signal
  primary-cell assignments, 35 deferred electronics, 65 obvious non-profile
  drafts and 174 conservative holds.
- Applied the two category assignments and removed 100 non-public RB market
  links. Canonical products and other markets were not deleted or changed.
- Reached 462 products that were not present in the previous 685-record
  enrichment queue.

## Live state after apply

| Metric | Before | After |
|---|---:|---:|
| RB site products | 7,115 | 7,015 |
| Exactly one category | 6,839 | 6,841 |
| Multiple categories | 0 | 0 |
| No category / hold | 276 | 174 |
| Strictly complete cards | 44 / 7,286 | 44 / 7,286 |

The strict completeness counter intentionally did not increase: taxonomy and
scope cleanup do not substitute for both an applied source-backed description
and a verified publishable exact-product image.

## Queue rollover

- Previous queue: 685 records.
- Hold members skipped from queue selection: 462 (381 missing stable identity,
  81 members of researched model clusters).
- New queue: 685 records, including 462 newly reached products and 223 carried
  records that still have another open gate.
- New official-source research: 75 clusters; 9 old clusters were recognized
  from the registry and were not repeated.

## Verification

- Python triage tests: 7 passed.
- Python uncategorized action-builder tests: 7 passed.
- Laravel enrichment queue tests: 3 passed, 21 assertions.
- Category assignment dry-run: 2/2 accepted; apply: 2 created.
- Scope exclusion dry-run: 100/100 non-public; apply: 100 links removed.
- Post-apply tree query: 7,015 site products; 6,841 with exactly one category;
  174 without a category; zero multi-category products.
- `seo:audit microchips-by --json`: 119 URLs checked, zero blocking issues.
- Docker services: backend, frontend, nginx, PostgreSQL and Redis healthy.

## Main artifacts

- `docs/imports/rb-research-holds-wave-120.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-120-known-hold-members.csv`
- `docs/audits/generated/rb-current-uncategorized-wave120-agent-review.csv`
- `docs/audits/generated/rb-current-uncategorized-wave120-actions-summary.json`
- `docs/audits/generated/rb-enrichment-queue-wave-120-backfill.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-120-backfill-summary.json`

No commit or push was performed.
