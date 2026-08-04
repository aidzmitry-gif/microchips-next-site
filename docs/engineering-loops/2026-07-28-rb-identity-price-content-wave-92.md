# RB identity, price and content wave 92 — 2026-07-28

## Scope

This wave continues the Belarus catalogue from the current database state. It
does not repeat the earlier 1C inventory, taxonomy or duplicate passes.

- only products already present in the 1C inventory were considered;
- `seo:electronic-components` remained excluded;
- the legacy Microchips price wins when it exists;
- a future current 1C price may be used only as `source_price × 2` when its
  currency, price type, observation date and exact product identity are all
  present;
- price never implies stock and this wave did not change availability.

## Identity and price result

Four pending Bitrix ↔ 1C pairs passed the existing fail-closed review command
after exact model checks and manufacturer-source verification:

| Candidate | 1C external ID | Model | Primary evidence |
| ---: | --- | --- | --- |
| 62 | `КА-00004142` | CSB GPL12400 | official CSB GPL12400 datasheet |
| 78 | `ФР-00001144` | Panasonic LC-R127R2PG1 | official Panasonic VRLA catalogue |
| 80 | `ФР-00002243` | Sprinter XP12V2500 | official Exide Sprinter P/XP catalogue |
| 101 | `КА-00005871` | Delta HRL12-170W | manufacturer-branded Delta product page |

The evidence command passed dry-run before apply. The price manifest was then
rebuilt from approved identities and the Bitrix snapshot dated 2026-06-23.

- manifest rows: 51 `legacy_site`, 0 `one_c_x2`;
- new price evidence: 4;
- existing evidence unchanged: 47;
- second apply: 0 evidence created, 0 prices updated;
- current RB price evidence/site prices: 53;
- publication and availability changes caused by price import: 0.

The current 1C inventory still contains no usable price, currency or price-type
columns, so the approved ×2 fallback remains implemented and tested but did
not run against any product.

APC APCRBC152 remains blocked. Schneider Electric describes APCRBC152 as a
12 V, 5.1 Ah replacement cartridge, contradicting the legacy/1C 48 V, 36 Ah
claim. It received no identity approval, price or migrated specification.

## Source-backed content and preview result

Three exact-model descriptions were staged, dry-run applied and then applied:

| 1C external ID | Product | Verified facts source |
| --- | --- | --- |
| `КА-00003848` | FIAMM 12FIT60 | official FIAMM FIT series table |
| `КА-00005708` | APC SRT192BP2 | official Schneider Electric product page |
| `КА-00005756` | IPPON Innova G2 1000 | official IPPON product page, ID 427357 |

The old SRT192BP2 title contained an unsupported `10Ah` claim. The source-backed
card now states only the verified 192 V battery-system facts and the rendered
page contains no `10Ah`/`10 А·ч` claim.

Together with the already described Delta DTM 1233 L, four products passed the
bounded preview command and now have unique HTTP 200 `noindex` pages. No Offer,
indexable URL, price or stock assertion was created by preview publication.

## Image gate

Five exact legacy `b_file` relations were extracted from the company backup and
visually inspected. Only two images proved the exact model on the visible
label and were imported:

- Delta DTM 1233 L — label shows `DTM 1233 L`, `12V 33Ah`;
- FIAMM 12FIT60 — label shows `12FIT60`, `12V 60Ah C10`.

Three assets were rejected from publication because their visible fronts did
not prove the exact SKU:

- APC SURT192RMXLBP;
- APC SRT192BP2;
- IPPON Innova G2 1000.

The two accepted rasters passed SHA-256, MIME, rights-basis, canonical MPN and
published-site-product guards. Repeated dry-run reported 2 unchanged and 0 new.

## Verified counters after the wave

- RB site products: 7,163;
- published noindex previews: 37;
- current site prices with evidence: 53;
- approved identity candidates: 54; pending: 54; rejected: 1;
- applied source-backed descriptions: 160;
- storefront-ready verified media: 32;
- strict non-electronic content-complete cards: **32 / 7,286 = 0.44%**;
- remaining cards in the fixed first-10% queue: 697.

This is a real `+2` strict-card increase (`30 → 32`), not a ten-percentage-point
milestone. The full-catalogue goal remains active.

## Verification

- targeted PHPUnit: 21 tests, 142 assertions, all passed;
- targeted Vitest: 2 files, 23 tests, all passed;
- SEO audit: 48 URLs, 0 blocking issues;
- four new product pages: HTTP 200, H1 present, `noindex` present;
- media present on the two visually approved pages only;
- price reapply: idempotent, 0 changes;
- all four HTML prototypes passed `scripts/verify-rb-prototype.ps1`.

## Reproducible evidence

- `docs/imports/rb-ready-mpn-evidence-decisions-wave-92.json`
- `docs/imports/rb-price-evidence-wave-92.csv`
- `docs/imports/rb-source-backed-description-drafts-wave-92-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-92-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-92-2026-07-28.json`

