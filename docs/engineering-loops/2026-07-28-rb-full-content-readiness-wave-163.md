# RB full-catalog content readiness — wave 163

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 163 attached 1,700 additional exact Bitrix descriptions in two bounded
sub-waves of 1,000 and 700. The command-enforced maximum batch size of 1,000
was retained; each sub-wave had its own dry-run.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Cards with classified text evidence | 2,707 | 4,407 | +1,700 |
| Text-evidence coverage | 16.49% | 26.85% | +10.36 pp |
| Exact legacy description drafts | 2,465 | 4,165 | +1,700 |
| Eligible exact descriptions remaining | 13,588 | 11,888 | -1,700 |
| Published RB products | 16,415 | 16,415 | 0 |
| Published products with a price | 34 | 34 | 0 |
| Indexable product URLs | 0 | 0 | 0 |

Safe local media coverage remains 13,132 / 16,415 (80.0000%). This wave did
not alter media records.

## Readiness registry after the batch

| Readiness class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 3,804 |
| `legacy_text_only` | 361 |
| `legacy_preview_only` | 9,240 |
| `thin_unidentified` | 2,768 |

The 4,407-card text-evidence total is the sum of the first four classes. It is
a migration-completeness metric, not a claim that 26.85% of pages are ready
for search indexation.

## Verification

- first dry-run: 13,588 eligible, 1,000 selected;
- first apply: exactly 1,000 descriptions and 11 revalidation batches;
- second dry-run: 12,588 eligible, 700 selected;
- second apply: exactly 700 descriptions and 8 revalidation batches;
- final dry-run: exactly 11,888 eligible remain;
- PostgreSQL: 4,165 exact legacy drafts, 16,415 published products, 34 priced
  products and zero indexable product URLs;
- PHPUnit: 4 tests, 41 assertions passed;
- queue worker: all 19 revalidation jobs completed without an error;
- browser boundary sample `legacy-bitrix-2713`: exact title, rendered text,
  `/api/media/1974` at natural width 264 px, request-price state and
  `noindex, nofollow`.

## Safety boundary

Each mutation required the pinned source run, exact CSV row count and SHA-256,
exact Bitrix element identifier, normalized-name equality, a published
namespaced noindex product, and an empty description. Existing descriptions,
prices, availability, identities, media and SEO indexability were not
overwritten or inferred.

## Next step

Continue the 11,888-row exact-description queue in bounded waves. In parallel,
prioritize the reduced 2,768 `thin_unidentified` records for identity recovery
and primary/manufacturer-source research; legacy text alone must not make them
indexable.
