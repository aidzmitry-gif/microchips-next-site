# RB official Lenovo evidence and content — wave 166

Date: 2026-07-29. Site: `microchips-by`.

## Result

Wave 166 attached another 1,700 descriptions from the exact same Bitrix
element in bounded batches of 1,000 and 700. It also converted the first
official Lenovo source research into a reproducible evidence registry without
publishing incompatible or derived facts.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Cards with classified text evidence | 7,807 | 9,507 | +1,700 |
| Text-evidence coverage | 47.56% | 57.92% | +10.36 pp |
| Exact legacy description drafts | 7,565 | 9,265 | +1,700 |
| Eligible exact descriptions remaining | 8,488 | 6,788 | -1,700 |
| Published RB products | 16,415 | 16,415 | 0 |
| Published products with a price | 34 | 34 | 0 |
| Indexable product URLs | 0 | 0 | 0 |

Safe local media coverage remains 13,132 / 16,415 (80.0000%). Product and
external-ID counts remain 25,970 / 25,970, so this content-only wave created no
catalog identities or duplicates.

## Readiness registry after the batch

| Readiness class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 8,510 |
| `legacy_text_only` | 755 |
| `legacy_preview_only` | 4,534 |
| `thin_unidentified` | 2,374 |

The 9,507-card text metric is migration completeness, not SEO release
readiness. All migrated product URLs remain `noindex`; legacy text is not
reclassified as manufacturer-primary evidence.

## Official Lenovo gate

- 90 single-P/N candidates checked against 2,480 official Lenovo registry rows;
- 21 exact unique P/N matches;
- 13 voltage conflicts and one energy conflict recorded as holds;
- no compatibility, image, derived mAh or catalog identity field published;
- Dell, HP and ASUS public documentation did not provide a scalable exact-P/N
  source for the requested combination of compatibility, electrical facts and
  battery image, so those 293 records remain `needs_primary_source`.

## Cache correction

The Next.js revalidation endpoint now expires both affected page paths and the
site/catalog fetch tags. The backend sends the site key and domain with every
revalidation job. This prevents product images and descriptions from remaining
hidden behind a stale API fetch after a successful import.

## Verification

- first dry-run/apply: exactly 1,000 descriptions, 11 revalidation batches;
- second dry-run/apply: exactly 700 descriptions, 8 revalidation batches;
- final dry-run: exactly 6,788 eligible descriptions remain;
- queue: 19 jobs started, 19 completed, zero failures;
- PHPUnit: 7 tests, 45 assertions passed;
- Lenovo evidence builder: 2 tests passed;
- browser boundary `legacy-bitrix-18213`: exact title, 59-character legacy
  description, `/api/media/9837` at 800×800, request-price state and
  `noindex, nofollow`;
- primary-cells listing: 12/12 first-page images loaded after tagged cache
  invalidation; category coverage is 1,571 / 1,604 (97.94%).

## Files

- `backend/app/Jobs/RevalidateNextSite.php`;
- `backend/tests/Feature/RevalidateNextSiteTest.php`;
- `frontend/src/app/api/revalidate/route.ts`;
- `frontend/src/app/api/revalidate/route.test.ts`;
- `scripts/build-lenovo-official-battery-evidence.py`;
- `scripts/tests/test_build_lenovo_official_battery_evidence.py`;
- `docs/audits/generated/rb-lenovo-official-battery-evidence-wave166.csv`;
- `docs/audits/generated/rb-full-content-readiness-wave166-after.csv`;
- `docs/audits/generated/rb-full-content-thin-wave166-after.csv`.

## Next step

Continue the remaining 6,788 exact-description queue while separating the 69
Lenovo registry misses and the 293 Dell/HP/ASUS records into source-specific
research queues. Duplicate collapse remains blocked until immutable identity
and variant facts agree; title similarity alone is not sufficient.
