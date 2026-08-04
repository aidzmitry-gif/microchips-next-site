# RB laptop identity candidates and content — wave 165

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 165 created a fail-closed title-evidence registry for all 2,188 current
`thin_unidentified` laptop-battery cards and attached another 1,700 exact
Bitrix descriptions in bounded sub-waves of 1,000 and 700.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Cards with classified text evidence | 6,107 | 7,807 | +1,700 |
| Text-evidence coverage | 37.20% | 47.56% | +10.36 pp |
| Exact legacy description drafts | 5,865 | 7,565 | +1,700 |
| Eligible exact descriptions remaining | 10,188 | 8,488 | -1,700 |
| Published RB products | 16,415 | 16,415 | 0 |
| Published products with a price | 34 | 34 | 0 |
| Indexable product URLs | 0 | 0 | 0 |

Safe local media coverage remains 13,132 / 16,415 (80.0000%).

## Laptop identity-candidate registry

The registry is derived only from literal title text and does not update the
database.

| Metric | Result |
| --- | ---: |
| Selected laptop cards | 2,188 |
| Records with P/N candidate | 870 |
| Records without P/N candidate | 1,318 |
| Distinct primary P/N groups | 683 |
| Repeated P/N groups | 145 |
| Records in repeated groups | 332 |
| Variant/fact-conflict groups | 133 |
| Records with title-stated voltage | 2,107 |
| Records with title-stated capacity | 2,051 |
| Records with title-stated energy | 493 |

Identity-risk routing:

| Risk | Records |
| --- | ---: |
| `missing_part_number` | 1,318 |
| `single_candidate_needs_primary_source` | 506 |
| `variant_or_fact_conflict_hold` | 308 |
| `multiple_part_numbers_needs_exact_source` | 32 |
| `repeated_part_number_needs_exact_source` | 24 |

The largest repeated groups include `A32-M50` (6), `MR90Y` (5), and
`AS07A31`, `A32-K55`, `A32-N56`, `C4500BAT6`, `JC04` (4 each). Inspection
confirmed that repeated P/Ns can differ by voltage, capacity, OEM/original
status or package variant. Those groups are holds, not automatic duplicates.

Every registry record has `candidate_scope=title_only_unverified`,
`review_status=needs_primary_source`, `safe_to_apply=false`, and a SHA-256 of
the source identity row. The builder blocks mismatched total/selected counts
and duplicate external IDs.

## Readiness registry after the content batch

| Readiness class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 6,810 |
| `legacy_text_only` | 755 |
| `legacy_preview_only` | 6,234 |
| `thin_unidentified` | 2,374 |

The remaining thin cohort is 2,188 laptop, 173 industrial, 11 transport and 2
mobile cards. The laptop count remained unchanged, so the new 2,188-row
identity registry is still the exact current laptop thin set.

## Verification

- title-candidate builder: 3 tests passed;
- content importer/readiness: 4 tests, 41 assertions passed;
- first dry-run/apply: exactly 1,000 descriptions, 11 revalidation batches;
- second dry-run/apply: exactly 700 descriptions, 8 revalidation batches;
- final dry-run: exactly 8,488 eligible descriptions remain;
- PostgreSQL: 7,565 exact drafts, 16,415 published products, 34 priced products
  and zero indexable product URLs;
- queue worker: all 19 revalidation jobs completed without error;
- browser boundary sample `legacy-bitrix-11472`: exact title, rendered text,
  `/api/media/6075` at natural width 800 px, request-price state and
  `noindex, nofollow`.

## Files

- `scripts/build-rb-laptop-title-identity-candidates.py`;
- `scripts/tests/test_build_rb_laptop_title_identity_candidates.py`;
- `docs/audits/generated/rb-laptop-title-identity-candidates-wave165.csv`;
- `docs/audits/generated/rb-laptop-title-identity-candidates-wave165.summary.json`;
- `docs/audits/generated/rb-full-content-readiness-wave165-after.csv`;
- `docs/audits/generated/rb-full-content-thin-wave165-after.csv`.

## Next step

Use the 506 single-P/N candidates as the first official-source research queue.
Keep the 308 conflict records and all repeated/multi-P/N groups on hold. The
1,318 missing-P/N titles require exact compatibility/source discovery before
any identity or technical field can be applied.
