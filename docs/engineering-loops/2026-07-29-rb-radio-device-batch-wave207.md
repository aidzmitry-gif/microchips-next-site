# RB radio/device source batch — Wave207

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope and result

Wave207 closes the remaining **315 cards** from the no-repeat Wave205 queue. Together with Wave206, all 500 cards in that queue are now classified. Cumulative research coverage is **1,000 / 3,894 eligible B2B cards (25.68%)**; this is research coverage, not project readiness.

| Partition | Rows | Exact safe | Conflict | Compatibility only | No evidence / routed hold |
|---|---:|---:|---:|---:|---:|
| Motorola + Kenwood | 104 | 4 | 7 | 0 | 93 |
| Icom + Vertex + Baofeng + small battery brands | 58 | 2 | 3 | 1 | 52 |
| Identity/source-route triage | 153 | 0 | 0 | 0 | 153 |
| **Total** | **315** | **6** | **10** | **1** | **298** |

There is no overlap with Wave206. The triage partition assigned an actionable primary-source route to 151 cards and held `bitrix:25712` and `bitrix:25713`, because the source title does not identify a device, connector or pack form.

## Adversarial findings

- Nine strict Motorola manufacturer/model duplicate groups were detected and held; no duplicate canonical identities were created.
- All 74 Motorola cards remain unmodified because the official PDFs could not be captured as stable evidence snapshots. Search snippets were not accepted as authority.
- Seven Kenwood claims conflict with primary evidence; 19 more lacked exact evidence.
- Icom BP-234, BP-252 and BP-256 have technical conflicts in chemistry, capacity or voltage and were held.
- `bitrix:26300` only had Baofeng UV-5R compatibility evidence. Compatibility was not treated as proof of the replacement battery identity.
- The live PostgreSQL collision gate checked all six application candidates and found zero canonical identity collisions.

## Safe application

Only six exact first-party identities passed the unchanged Laravel gate:

| Import run | Manifest | Rows | Newly filled | Idempotent rerun |
|---:|---|---:|---:|---:|
| 928 | Icom BP-210N, BP-264 | 2 | 2 | 2 unchanged |
| 929 | Kenwood KNB-29N, KNB-41NC, KNB-53N, KNB-56N | 4 | 4 | 4 unchanged |

The application changed only blank `manufacturer` and `mpn` fields. Product names, SKUs, technical specifications, media, prices, availability and publication fields were unchanged. Every affected product remained behind the command's exactly-one-URL, schema-null, noindex preview gate.

## Verification

- targeted Wave207 tests: **20 passed**;
- both manifests passed Laravel dry-run before application;
- idempotence reruns: **0 filled / 6 unchanged**;
- commercial fields changed: **0**;
- publication fields changed: **0**;
- final SEO audit: **16,853 URLs, 97 redirects, 0 blockers**.

## Main artefacts

- `docs/audits/generated/wave207-motorola-kenwood-evidence.csv`
- `docs/audits/generated/rb-wave207-device-small-evidence.csv`
- `docs/audits/generated/rb-wave207-identity-triage.csv`
- `docs/imports/rb-verified-oem-identities-wave207-motorola-kenwood-2026-07-29.json`
- `docs/imports/rb-verified-oem-identities-wave207-device-small-2026-07-29.json`
- `docs/audits/sources/wave207-motorola-kenwood/`
- `docs/audits/sources/wave207-device-small/`

Wave207 materially advances catalog identity research and closes the second 500-card queue. It does not increase overall project readiness because verified descriptions, media, current commercial data and indexability still require independent release evidence.
