# RB full-catalog content readiness — wave 167

Date: 2026-07-29. Site: `microchips-by`.

## Result

Wave 167 attached 1,700 additional descriptions from the exact same Bitrix
element in bounded batches of 1,000 and 700.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Cards with classified text evidence | 9,507 | 11,207 | +1,700 |
| Text-evidence coverage | 57.92% | 68.27% | +10.35 pp |
| Exact legacy description drafts | 9,265 | 10,965 | +1,700 |
| Eligible exact descriptions remaining | 6,788 | 5,088 | -1,700 |
| Published RB products | 16,415 | 16,415 | 0 |
| Published products with a price | 34 | 34 | 0 |
| Indexable product URLs | 0 | 0 | 0 |

Safe local media coverage remains 13,132 / 16,415 (80.0000%). Products and
distinct external IDs remain 25,970 / 25,970.

## Readiness after the batch

| Class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 10,209 |
| `legacy_text_only` | 756 |
| `legacy_preview_only` | 2,835 |
| `thin_unidentified` | 2,373 |

The thin cohort is now 2,188 laptop, 173 industrial, 11 transport and one
mobile card. Legacy text remains migration evidence only, and all product URLs
remain `noindex`.

## Verification

- first dry-run/apply: 1,000 descriptions and 11 revalidation batches;
- second dry-run/apply: 700 descriptions and eight revalidation batches;
- final dry-run: exactly 5,088 eligible descriptions remain;
- exact drafts: 10,965 rows for 10,965 distinct products;
- browser boundary `legacy-bitrix-19970`: exact title, 47-character source
  description, `/api/media/11536` at 936×1000, request-price state and
  `noindex, nofollow`;
- queue aggregate for waves 166–167: 38 started, 38 completed, zero failures.
