# RB owned media and preview wave 7 — 2026-07-27

## Result

- Added 16 source-backed RB catalogue cards to the local storefront as `noindex,follow` previews.
- Imported 16 exact-model images from the company-owned Bitrix upload backup.
- No price, stock, offer or indexable URL was created.
- Fixed-baseline content-complete count increased from 14 to 30 of 7,286 (`0.41%`).
- The first 10% enrichment queue now contains 699 remaining cards toward the 729-card target.

## Safety gates

- Bitrix detail-picture relation rechecked against `user_microchips_data.sql.gz`.
- Machine-vision identity QA: 16 PASS, 0 FAIL, 0 UNCLEAR.
- SHA-256 validated for every imported raster.
- Preview dry-run: 16 products, 2 categories, 0 indexable URLs, 0 offers.
- Media dry-run before apply: 16 new files.
- Media idempotence dry-run after apply: 16 unchanged, 0 new.
- SEO audit: PASS, 42 URLs, 0 redirect errors.
- SSR regression: all 16 product URLs returned HTTP 200, `noindex`, and a local media URL.

## Data notes

- Delta DTM 1215 image label states 14.5 Ah. The old title's rounded 15 Ah must not override manufacturer-backed specification evidence.
- Ventura GPL 12-200 and Vostok PRO SK-1218 images are lower resolution than the rest, but their exact model labels remain unambiguous.
- All 16 assets retain the Microchips watermark and have the rights basis `Company-owned Microchips legacy Bitrix upload backup` in the media ledger.

## Reproducible artifacts

- `docs/imports/rb-source-verified-preview-wave-7-2026-07-27.json`
- `docs/imports/rb-verified-legacy-images-wave-7-2026-07-27.json`
- `docs/audits/generated/rb-owned-media-wave-7/assets/`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.csv`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.summary.json`

The regenerated queue is UTF-8 with BOM and contains neither Unicode replacement characters nor mojibake. After duplicate waves 76-78, CSV SHA-256: `B7D326695F99C9CFD60BED34EC997F3C99B73B997B5DE06FFF5E279492B829CD`.

## Progress accounting

This wave is evidence of real progress but is not a +10 percentage-point milestone. Under the fixed denominator, 30 cards are content-complete, so the verified content-completeness metric is `30 / 7,286 = 0.41%`.
