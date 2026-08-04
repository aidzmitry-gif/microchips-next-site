# Wave243–244 — official content and verified duplicate collapse

Date: `2026-07-30`  
Site: `microchips-by`

## Outcome

The cycle reviewed 276 frozen B2B battery cards without replaying previously
used source URLs or snapshot hashes.

- New exact OEM identities applied: **20** (`Delta 6`, `Fiamm/Panasonic 13`,
  `APC 1`).
- New manufacturer-primary descriptions applied: **20**.
- Verified regional duplicates collapsed into existing canonical 1C owners:
  **11** (`Delta 5`, `Fiamm 4`, `APC 2`).
- Exact active 301 redirects created: **11**.
- Canonical products deleted: **0**.
- Two additional APC duplicate candidates remained `HOLD_FAIL_CLOSED` because
  their Bitrix cards have independent prices (`790` and `1035 BYN`) and current
  price-evidence rows.

The first refreshed Fiamm/Panasonic and APC description dry-runs rejected
display names that did not end with the canonical MPN. Their builders and tests
were corrected before any description write. The successful reruns refreshed
and applied all 20 descriptions without publication or commercial changes.

## Commercial and publication invariants

| Metric | Before | After |
|---|---:|---:|
| Site products | 24,298 | 24,287 |
| Published site products | 16,816 | 16,805 |
| Active redirects | 97 | 108 |
| Numeric prices | 1,067 | 1,067 |
| Current price evidence | 1,067 | 1,067 |
| Applied descriptions | 1,621 | 1,641 |

All retained prices still use `availability=on_request`; this cycle did not add
`InStock` or `Offer` claims.

## Current readiness evidence

- Eligible published site products: **16,805**.
- Content-complete cards: **395**.
- `strict_content_ready`: **216**.
- `source_backed_partial`: **1,101** (`+20`).
- Fixed 10% enrichment queue: **1,247**.
  - description present: **922**;
  - description missing: **325**;
  - verified strict image present inside this queue: **0**.
- Wave244 queue inherited **270** no-repeat research decisions and admitted only
  six newly exposed replacement rows after duplicate retirement.

Overall confirmed project readiness remains **60%**. Identity, description and
duplicate correctness improved materially, but strict reusable image coverage,
remaining catalogue review and launch gates do not yet prove 70%.

## Verification

- Wave243 Python builders/queue: `12 passed` in their isolated suites.
- Wave244 builders/queue: `8 passed`.
- Laravel duplicate command: `4 tests, 33 assertions`.
- Frontend catalogue/product/API/page regression: `45 passed`.
- HTML prototype contract: `4/4 passed`.
- SEO release audit: `16,842 URLs`, `108 redirects`, `0 blockers`.
- Runtime: all six Docker services healthy after rebuild.
- HTTP check: legacy `bitrix:1488` returns `301` to canonical
  `/catalog/industrial-batteries/batteries-ups/fiamm-fg21202`.
- Canonical runtime card retains `85.00 BYN`, evidence date `2026-06-23`, exact
  MPN `FG21202`, verified technical content and `schema=null` while noindex.
- `git diff --check`, PHP syntax and Python syntax checks passed.

## Primary evidence artifacts

- `docs/audits/generated/rb-enrichment-queue-wave244.csv`
- `docs/audits/generated/rb-full-content-readiness-wave244-after.csv`
- `docs/imports/rb-reviewed-delta-duplicates-wave243-2026-07-29.json`
- `docs/imports/rb-reviewed-fiamm-duplicates-wave244a-2026-07-30.json`
- `docs/imports/rb-reviewed-fiamm-duplicates-wave244b-2026-07-30.json`
- `docs/imports/rb-verified-noindex-duplicate-collapse-wave244c-2026-07-30.json`

No commit or push was performed.
