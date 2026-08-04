# Wave245 — usable facets and the six replacement B2B rows

Date: `2026-07-30`  
Site: `microchips-by`

## Outcome

This cycle closed the six replacement rows introduced after Wave244 duplicate
retirement and improved live catalogue navigation without replaying prior source
research.

- Four new Panasonic cards received exact OEM identities and manufacturer-primary
  descriptions: `LC-XC1222P`, `LC-XC1228P`, `LC-XC1238P`, and `UP-VW0645P1`.
- `UP-VW1220P1` remains fail-closed because two exact unpublished 1C candidates
  exist. `LC-XD1217PG` remains fail-closed because bounded discovery did not find
  a new exact primary source.
- Exact Panasonic product images were extracted and visually checked, but none
  were imported: the manufacturer terms do not grant storefront redistribution
  rights without prior permission.
- No duplicate collapse was required for the four applied rows; each has one live
  Bitrix owner and no exact 1C owner.
- Prices, availability, publication state, and redirects were not changed.

## Facet UX

The battery catalogue now normalizes aliases instead of presenting source-system
spelling variants as separate filters.

- manufacturer aliases collapse to canonical brands;
- technologies collapse to four meaningful values in the live UPS-battery slice;
- voltage uses canonical numeric `V` values;
- exact capacity remains on every product card, while the filter uses seven
  customer-facing ranges.

Live `/catalog/industrial-batteries/batteries-ups` evidence:

| Metric | Result |
|---|---:|
| Products | 1,221 |
| Manufacturer options | 18 |
| Technology options | 4 |
| Voltage options | 10 |
| Capacity ranges | 7 |

Raw input `7,2 А·ч` and canonical bucket `5–10 Ah` both resolve to the same
38-product result set. Filter parameters remain a non-indexable UX state rather
than new SEO landing pages.

## Catalogue and commercial invariants

| Metric | Current |
|---|---:|
| Site products, all states | 24,337 |
| Published regional products | 16,805 |
| Numeric prices | 1,067 |
| Current price-evidence rows | 1,067 |
| Applied descriptions | 1,645 |
| Active redirects | 108 |

Wave245 readiness registry:

- eligible published products: **16,805**;
- content-complete cards: **395**;
- `source_backed_partial`: **1,105** (`+4`);
- `strict_content_ready`: **216**;
- fixed 10% enrichment queue: **1,247**;
  - description present: **926**;
  - description missing: **321**;
  - verified reusable image present in this queue: **0**.

The fixed-baseline deep-content completion is `395 / 16,415 = 2.41%`.
Overall confirmed project readiness remains **60%**: this cycle improves catalogue
quality, but reusable media coverage, remaining catalogue research, launch index
promotion, and post-launch observation do not prove the 70% gate.

## Verification

- Catalogue API: `18 tests, 154 assertions`.
- OEM and description workflow: `34 tests, 189 assertions`.
- Wave245 Python evidence/queue: `7 passed`.
- Frontend: `20 files, 102 tests`.
- HTML prototype contract: `4/4 passed`.
- SEO release audit: `16,842 URLs`, `108 redirects`, `0 blockers`.
- Live facet runtime: `1,221` products and `7` capacity ranges.
- Docker: all six services healthy.
- PHP/Python syntax and scoped `git diff --check`: passed.

## Primary artifacts

- `docs/audits/generated/rb-enrichment-queue-wave245.csv`
- `docs/audits/generated/rb-enrichment-queue-wave245.summary.json`
- `docs/audits/generated/rb-full-content-readiness-wave245-after.csv`
- `docs/imports/rb-verified-oem-identities-wave245a-panasonic-2026-07-30.json`
- `docs/imports/rb-verified-oem-identities-wave245b-panasonic-2026-07-30.json`
- `docs/imports/rb-verified-oem-identities-wave245c-panasonic-2026-07-30.json`
- the three matching source-backed description manifests.

No commit or push was performed.
