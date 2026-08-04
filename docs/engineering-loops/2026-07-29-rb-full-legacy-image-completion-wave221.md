# RB exact legacy image completion — Wave221

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Result

The pinned full Bitrix run `763` contains company-owned product uploads with an exact element → PREVIEW/DETAIL_PICTURE relation. The guarded adopter was run in three bounded apply batches:

| Batch | Eligible before | Created | Remaining |
|---:|---:|---:|---:|
| 1 | 2,188 | 500 | 1,688 |
| 2 | 1,688 | 1,000 | 688 |
| 3 | 688 | 688 | 0 |
| **Total** | | **2,188** | **0** |

The final dry-run selected 0 records. Current database state contains **15,232** published `legacy_bitrix_exact_element_preview` media rows and **0 products with duplicate links of this source kind**.

## Safety boundary

- every file belongs to the company's own Microchips Bitrix backup;
- every media row is attached to the exact namespaced Bitrix element, not a title-similar product;
- raster integrity, size and SHA-256 are checked before insertion;
- only published `on_request`, unpriced noindex preview products from source run 763 are eligible;
- indexable pages changed: 0;
- prices, stock, product identity and technical claims changed: 0;
- status remains `legacy_exact_preview`, not visually/OEM verified.

The images are therefore usable for the migrated noindex preview catalogue, while final indexability still requires model-level visual or manufacturer verification.

## Verification

- source run 763: 17,207 staged records; 16,880 materialized products;
- extracted legacy assets: 15,336;
- eligible missing exact images after final apply: 0;
- duplicate exact-preview media per product: 0;
- post-change readiness registry: `docs/audits/generated/rb-full-content-readiness-wave221-after.csv`;
- post-change enrichment queue: `docs/audits/generated/rb-enrichment-queue-wave221.csv`.

This wave materially improves the storefront without copying unknown internet images or falsely labelling legacy photographs as manufacturer-verified assets.
