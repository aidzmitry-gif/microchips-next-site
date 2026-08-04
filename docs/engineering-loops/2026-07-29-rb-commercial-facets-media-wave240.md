# RB commercial truth, scoped facets and FIAMM media — Wave240

Date: `2026-07-29`  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

Wave240 makes verified legacy commercial data useful without turning price into
an invented stock claim. The exact Bitrix snapshot is pinned by SHA-256 and a
new fail-closed route emits prices only for a published
`bitrix:<legacy_element_id>` product when the source row is unique, positive
BYN data from `bitrix_backup_2026-06-23`, no identity candidate exists for that
legacy ID and the product has no current price evidence.

The frozen price manifest contains 1,065 rows:

- 1,010 new direct Bitrix prices;
- 55 existing approved Bitrix ↔ 1C identity prices;
- 0 `one_c_x2` rows because the authoritative 1C snapshot still contains no
  positive price, currency or price-type values.

The importer dry-run validated all 1,065 rows without mutations. The apply
created 1,010 evidence rows and updated exactly 1,010 site prices. A second
apply created 0 evidence rows and updated 0 prices. Publication and
availability were unchanged on both runs.

## Commercial integrity after apply

- numeric prices: 57 → **1,067**;
- published numeric-price cards: 34 → **1,044**;
- current price-evidence rows: 57 → **1,067**;
- current legacy-site evidence: **1,067**;
- current `one_c_x2` evidence: **0**;
- visible price without current evidence: **0**;
- evidence/value mismatch: **0**;
- duplicate current evidence: **0**.

Price still does not imply availability. The importer does not write
availability, publication or schema. Runtime verification of FIAMM
`12FLB400 P` returned price `718.50 BYN`, `availability=on_request` and its
verified image. The release auditor continues to suppress `Offer` unless
independently confirmed in-stock commercial data matches the visible price.

## Scoped catalogue controls

Price sorting is now enabled only when current source-backed price evidence
exists inside the current category or search scope. Runtime verification:

- root catalogue: `price_sort_enabled=true`; ascending prices start at
  `0.20`, `0.43`, `7.00` BYN;
- search `BR2032`: nine unpriced results, `price_sort_enabled=false`;
- requesting `sort=price_asc` for that unpriced search returns HTTP 422.

Unapplied facets are now shown only when at least
`max(10, ceil(scope_total × 10%))` records contain the facet. An applied sparse
facet remains visible, so a bookmarked or shared filter never disappears.
This prevents low-coverage filters and hundreds of singleton capacity values
from looking like complete navigation. Two exact FIAMM capacity keys from
Wave239 are now included in extraction.

## Exact FIAMM media

Original-resolution review against SHA-pinned authorised FIAMM brochures
confirmed three company-owned legacy assets:

- `bitrix:1427` — `12FLB400 P`, media `191`;
- `bitrix:3241` — `12SLA80L`, media `934`;
- `bitrix:3267` — `12FGHL34`, media `956`.

The promotion dry-run reported three records and zero mutations. Apply
promoted 3/3, touched three site products and changed zero publication or
commercial fields. Content-complete cards increased 392 → **395** and strict
content-ready cards 213 → **216**; the deterministic 10% enrichment queue
decreased 1,250 → **1,247**.

## Verification

- price builder tests: 8 tests, 56 assertions — PASS;
- price importer + scoped catalogue tests: combined relevant suite PASS;
- scoped catalogue test file: 17 tests, 136 assertions — PASS;
- legacy media promotion core tests: 3 tests, 28 assertions — PASS;
- full combined host run: 29 price/catalogue tests passed; four pre-existing
  media-test harness cases initially failed only because the host invocation
  omitted `fileinfo` and PHPUnit 12 no longer consumes the old docblock data
  provider; the three executable command paths passed after loading `fileinfo`;
- price builder dry-run: 1,065 validated, zero mutations;
- price apply: 1,010 created/updated; idempotence 0/0;
- media dry-run/apply: 3 validated, 3 promoted, zero commercial/publication
  changes;
- price SQL audit: all three integrity counters zero;
- runtime API checks: root priced sort PASS, unpriced search 422 PASS, FIAMM
  image/price/on-request PASS;
- SEO release audit with 512 MB audit memory: **16,853 URLs, 97 redirects,
  0 blockers**;
- four RB HTML prototypes: PASS.

## Evidence

- Bitrix source manifest SHA-256:
  `e454389508b4bc3f928650b7871ff31baad8100ab634593ae4ec3618ba388706`;
- price manifest:
  `docs/imports/rb-price-evidence-wave240-2026-07-29.csv`;
- price manifest SHA-256:
  `eb740bf443bfe31b251de859a6a69ad2bb8d9237500ce663ca09ee354e850eea`;
- media manifest:
  `docs/imports/rb-reviewed-legacy-preview-media-wave240c-fiamm-2026-07-29.json`;
- media manifest SHA-256:
  `314a327665d3affa4271df7848c33f27fb85802329cb4752123fdd25a8c619e3`;
- Wave240 enrichment queue:
  `docs/audits/generated/rb-enrichment-queue-wave240.csv`;
- Wave240 readiness audit:
  `docs/audits/generated/rb-full-content-readiness-wave240-after.csv`.

Overall readiness remains 60% because this cycle materially improves
commercial coverage and catalogue usability but does not complete another
weighted country-launch gate. The next no-repeat cycle should enrich the next
B2B queue batch with exact manufacturer media and descriptions while keeping
the new 1,010 legacy prices under freshness monitoring.
