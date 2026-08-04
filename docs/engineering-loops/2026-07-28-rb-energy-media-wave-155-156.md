# RB energy-device media transfer — waves 155–156

Date: 2026-07-28. Site: `microchips-by`.

## Scope and result

Wave 155 processed `rechargeable-cells`, `chargers` and `power-systems` in one
archive pass. Wave 156 added the smallest safe package needed to cross the next
10% progress threshold: `batteries-traction` and `warehouse-equipment`.

| Metric | Result |
| --- | ---: |
| Wave 155 staging rows | 2,101 |
| Wave 155 safe same-element media rows | 2,016 |
| Wave 155 newly attached images | 1,657 |
| Wave 156 staging rows | 203 |
| Wave 156 safe same-element media rows | 195 |
| Wave 156 newly attached images | 195 |
| Rejected/corrupt archive images | 0 |
| RB published products | 16,415 |
| RB products with displayable local media | 4,975 (30.31%) |
| Strict visually verified media | 88 |
| Indexable product pages | 0 |

Existing images were not duplicated: the adoption command selected only
products missing a `legacy_exact_preview` row. Final dry-runs returned zero
eligible records.

## Category evidence

| Category | Published | With displayable media | First API page |
| --- | ---: | ---: | ---: |
| Rechargeable cells | 1,115 | 1,080 | 24/24 images |
| Chargers | 293 | 272 | 24/24 images |
| Power systems (direct category) | 666 | 664 | aggregate API 24/24 images |
| Traction batteries | 159 | 159 | 24/24 images |
| Warehouse equipment | 39 | 39 | 24/24 images |

## Queue efficiency

The first 1,000-image transaction generated 11 revalidation jobs, the next 657
generated 7, and the final 195 generated 2. URLs are chunked in batches of 100;
the previous per-product pattern would have generated 1,852 separate jobs.
Horizon logs show every observed `RevalidateNextSite` job completed.

## Safety and runtime verification

- source identity: exact `DETAIL_PICTURE`/`PREVIEW_PICTURE` relation from the
  same Bitrix element only;
- 1C products, duplicate candidates and collision holds were not mutated;
- no price, stock, structured offer or indexability was inferred;
- five sampled media endpoints returned HTTP 200, valid JPEG/PNG content and
  `X-Robots-Tag: noindex, noarchive` plus `Cache-Control: private, no-store`;
- browser check of `/catalog/chargers`: 293 total, 12/12 rendered images,
  zero placeholders and all images loaded with non-zero intrinsic dimensions;
- final adoption dry-run: `eligible_missing_preview_media = 0`.

## Remaining

The 30.31% number is safe preview coverage, not strict SEO readiness. Promotion
to indexable pages still requires confirmed canonical identity, manufacturer
facts, a source-backed description and visually verified media.
