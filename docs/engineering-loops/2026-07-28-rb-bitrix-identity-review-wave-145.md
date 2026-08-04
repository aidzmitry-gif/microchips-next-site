# RB Bitrix ↔ 1C identity review — wave 145

Date: 2026-07-28  
Scope: the 22 single-high-signal rows isolated from 88 mapping-collision groups in wave 144.

## Result

All 22 rows received an explicit, fail-closed decision:

- 18 `same_identity` links were confirmed by exact manufacturer/model evidence;
- 3 rows remain `hold` because a terminal or historical model variant is not proven;
- 1 row is `different_product_false_mapping`: legacy `Delta DTM 12100 I` must not be linked to 1C `Delta DTM 12100 L`.

The applied relation is audit evidence, not a product merge. Import run `755` contains all 22 reviewed decisions. Only the 18 exact links were added to `catalog_identity_candidates` with status `same_identity_confirmed`. The command deliberately does not change products, site links, families, publication, URLs, SEO, prices or media.

## Primary-source corrections

- CSB confirms `HR1221W` with an F2 Faston terminal in the [official HR1221W datasheet](https://csb-battery.com/wp-content/uploads/2024/07/CSB-Datasheet-HR1221W-%E2%80%93-053124.pdf).
- CSB confirms `GP12120`, 12 Ah and F2 terminal in the [official GP12120 datasheet](https://csb-battery.com/wp-content/uploads/2024/07/CSB-Datasheet-GP12120-%E2%80%93-053124.pdf).
- Delta confirms the exact `FT 12-125 M`, 12 V, 125 Ah and M8 execution on the [official product page](https://www.delta-battery.ru/catalog/ft-m/delta-ft-12-125-m/).
- B.B. Battery lists multiple terminal options for `BC17-12`; therefore the legacy row without a readable B1 mark remains on hold despite a compatible local photo. See the [official BC17-12 page](https://www.bb-bat.com/en/product/BC1712.html).
- Current official Ventura catalogues do not establish the historical `FT12-50` identity, so that row remains on hold rather than being merged.

## Database proof

Before apply:

| Entity | Count |
|---|---:|
| products | 9,084 |
| site_products | 7,061 |
| product_families | 1 |
| site_urls | 264 |
| site_seos | 253 |
| product_media | 85 |
| catalog_identity_candidates | 109 |
| import_runs | 749 |

After apply:

| Entity | Count |
|---|---:|
| products | 9,084 |
| site_products | 7,061 |
| product_families | 1 |
| site_urls | 264 |
| site_seos | 253 |
| product_media | 85 |
| catalog_identity_candidates | 127 |
| import_runs | 750 |

Only the expected evidence records increased: `+18` identity links and `+1` reviewed import run. A repeated apply returned `unchanged=true` and created no records.

## Verification

- JSON manifest parsed successfully.
- Real PostgreSQL dry-run: 22/22 decisions passed all source-run, text-hash, 1C identity, RB site-link and product-identity guards.
- Feature tests: `2 tests, 20 assertions` passed in the isolated `microchips_test_wave145` PostgreSQL database.
- Combined identity + preview regression: `5 tests, 66 assertions` passed.
- Pint: both new PHP files pass.
- Apply: run `755`, 18 exact links, 3 holds, 1 false mapping.
- Replay: `unchanged=true`.
- Live API check after container rebuild:
  - Bitrix `1479` → `confirmed`, canonical `КА-00001615`;
  - Bitrix `1526` → `hold`, no canonical external ID;
  - Bitrix `20116` → `rejected_mapping`, no canonical external ID;
  - `/legacy-preview/catalog` → HTTP 200 with `X-Robots-Tag: noindex, nofollow, noarchive`.

## Readiness impact

- The bounded 22-row identity gate is now **100% reviewed**.
- Safe legacy-preview transfer remains **90%**; this wave removes identity risk but does not complete the URL/redirect migration gate.
- Strict content-complete canonical readiness remains **77 / 7,286 = 1.06%**, because an identity link alone is not proof of description, verified media, commercial data and publishable SEO content.
- No artificial +10 percentage-point milestone is claimed.

Next highest-value step: consume the 18 confirmed links in the read-only legacy preview and source-backed enrichment queue, while the three holds remain excluded. Search Console data will be used later for the URL/301 release gate after the user signs in.
