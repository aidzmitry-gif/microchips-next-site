# RB replacement-device media transfer — wave 157

Date: 2026-07-28. Site: `microchips-by`.

## Scope and result

This wave selected the smallest controlled package that could move safe local
preview coverage past the next 10% threshold without processing the two very
large laptop and mobile categories in the same archive cycle.

| Metric | Result |
| --- | ---: |
| Categories | 4 |
| Staging rows considered | 1,964 |
| Safe same-element Bitrix media rows | 1,839 |
| Exact source file references found | 1,839 |
| Extracted raster assets | 1,839 |
| Rejected/corrupt assets | 0 |
| Local asset bytes | 137,372,043 |
| Newly attached preview images | 1,839 |
| Revalidation batches | 20 |
| RB published products | 16,415 |
| RB products with displayable local media | 6,814 (41.51%) |
| Strict visually verified products | 88 |
| Indexable product URLs | 0 |

## Category evidence

| Category | Published | With displayable media | Browser first page |
| --- | ---: | ---: | ---: |
| Photo, video and audio equipment batteries | 827 | 827 | 12/12 loaded |
| Medical equipment batteries | 408 | 408 | 12/12 loaded |
| Power-tool batteries | 316 | 316 | 12/12 loaded |
| Home-appliance batteries | 288 | 288 | 12/12 loaded |

All four browser checks returned zero broken images and zero placeholder cards.

## Exclusions and safety

Of 1,964 scoped staging rows, 125 were not mutated:

- 6 inactive legacy rows;
- 1 existing exact 1C link;
- 2 duplicate candidates;
- 4 linked-identity candidates;
- 112 1C collision holds.

Every attached image came from the exact `PREVIEW_PICTURE` or
`DETAIL_PICTURE` relation of the same Bitrix element. Names and fuzzy matches
were not used. The 1,839 affected products remain unpriced and non-indexable;
the wave did not infer stock, model identity or commercial data.

## Verification

- final importer dry-run: `eligible_missing_preview_media = 0`;
- PostgreSQL: 6,814 / 16,415 displayable local media = 41.51%;
- category counts: 1,839 / 1,839 cards have displayable media;
- browser: four pages, 48 / 48 first-page images loaded with non-zero intrinsic
  dimensions, zero broken images and zero placeholders;
- sample `/api/media/5010`: HTTP 200, `image/jpeg`, `X-Robots-Tag:
  noindex, noarchive`, `Cache-Control: private, no-store`;
- Horizon logs show all observed revalidation jobs completed successfully.

## Remaining

Safe preview coverage is not strict SEO readiness. The migrated pages stay
`noindex` until canonical identity, manufacturer facts, source-backed content
and visually verified media are confirmed. The largest remaining image gaps are
the mobile and laptop replacement-battery categories; they should be processed
in bounded waves rather than as one opaque operation.
