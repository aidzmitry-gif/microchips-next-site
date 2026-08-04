# RB primary-cells full media transfer — wave 154

Date: 2026-07-28. Site: `microchips-by`. Category: `seo:primary-cells`.

## Result

- The complete Bitrix media index now covers 21,132 catalogue elements; 21,113 have a source media reference.
- The `primary-cells` staging slice contains 1,630 Bitrix rows.
- 1,571 `legacy_only_draft_candidate` rows had an exact same-element image reference and were extracted without rejection.
- 1,571 images were attached to the corresponding namespaced Bitrix products in two bounded batches (1,000 + 571).
- 59 non-safe rows were not touched: 1 existing exact 1C link, 4 duplicate candidates, 22 linked-identity candidates and 32 1C collisions.
- The live category now contains 1,604 published products; 1,571 have displayable exact legacy preview media, 33 canonical 1C products remain in the source-backed enrichment queue.
- No category product is indexable, priced or given a stock claim by this wave.

## Safety model

The transferred image is selected only by the Bitrix element's own
`DETAIL_PICTURE` or `PREVIEW_PICTURE` file ID. Names, fuzzy matches and 1C
identity are not used. The resulting `legacy_exact_preview` media remains
distinct from visually verified media and is served with:

- `X-Robots-Tag: noindex, noarchive`;
- `Cache-Control: private, no-store, max-age=0`;
- the product page itself remains `noindex, nofollow`.

## UX correction

Default catalogue ordering now preserves explicit `sort_order`, then prefers
cards that have displayable local media. This avoids a placeholder-only first
page when older canonical 1C rows have lower database IDs. A PostgreSQL-specific
NULL ordering issue found by runtime verification was fixed by using a numeric
correlated count instead of a nullable scalar subquery.

## Evidence

- extractor self-test: passed;
- full Bitrix extraction: 2,856 B2B rows / 1,569 first-focus rows unchanged;
- category manifest: 1,571 media references, 0 missing index rows, 0 source rows without media;
- archive extraction: 1,571 raster files, 0 rejected, 330.22 MiB;
- importer idempotency: final dry-run selected 0 and remaining 0;
- database: 1,604 published / 1,571 displayable media / 0 indexable / 0 priced;
- API first page: 24 returned / 24 with image;
- browser first page: 12 cards / 12 loaded images / 0 placeholders / 0 broken images;
- product page `/catalog/primary-cells/legacy-bitrix-736`: HTTP 200, noindex, media present;
- media `/api/media/1571`: HTTP 200, `image/png`, 99,161 bytes, noindex/no-store headers;
- PHPUnit: `test_default_catalog_order_prefers_displayable_media_after_explicit_sort_order` passed, 7 assertions.

## Remaining work

The 33 canonical 1C products without media must be handled separately through
exact manufacturer/MPN evidence or a confirmed Bitrix-to-1C identity. They were
deliberately not assigned images from similar legacy names in this wave.
