# RB Bitrix/1C collision evidence — wave 144

## Result

All 430 rows previously labelled `candidate_duplicate_group` are now covered by
one fail-closed evidence manifest. They form 88 mapping-collision groups, not
430 proven duplicate groups.

| Group decision | Groups |
|---|---:|
| `mixed_mapping_collision_hold` | 40 |
| `single_high_signal_review_queue` | 22 |
| `variant_or_collision_hold` | 26 |

| Member decision | Members |
|---|---:|
| `hold_insufficient_identity_evidence` | 306 |
| `hold_multiple_high_signal_candidates` | 102 |
| `review_exact_identity_candidate` | 22 |

The first source-review queue therefore contains exactly 22 candidates. No
matcher score was converted into a duplicate merge automatically.

## Safety model

The manifest explicitly forbids product create/merge/delete, site-link changes,
family creation, publication, URL and SEO mutations, and legacy HTML rendering.
The Laravel importer validates those flags, verifies exact 88/430 coverage
against source snapshot ImportRun 742, verifies every legacy ID, 1C group and
legacy text hash, and rejects source drift or inconsistent summary counts.

The apply mode creates only an `ImportRun` and
`bitrix_duplicate_review_decision` staged evidence rows. It has no code path to
`Product`, `SiteProduct`, `ProductFamily`, `SiteUrl`, `SiteSeo` or publication
mutation.

## Local apply evidence

- source snapshot ImportRun: 742;
- evidence ImportRun: 754;
- staged evidence rows: 430;
- failed rows: 0;
- rows with a published product reference: 0;
- published RB site products after apply: 233 (unchanged from the transfer
  baseline);
- second apply: `unchanged=true`, no duplicate run or rows.

## Artifacts

- `scripts/build-bitrix-duplicate-review-evidence.py`
- `scripts/tests/test_build_bitrix_duplicate_review_evidence.py`
- `docs/imports/rb-bitrix-duplicate-review-evidence-wave144-2026-07-28.json`
- `docs/imports/rb-bitrix-single-high-signal-review-queue-wave144.csv`
- `backend/app/Console/Commands/StageBitrixDuplicateReviewEvidence.php`
- `backend/tests/Feature/StageBitrixDuplicateReviewEvidenceTest.php`

## Verification

- Python compile: passed;
- Python focused tests: 2 passed;
- generated manifest: exactly 88 groups / 430 members / 22 review rows;
- Laravel Pint: 2 files passed;
- isolated SQLite PHPUnit: 2 tests passed;
- real PostgreSQL dry-run: passed;
- real PostgreSQL apply: 430/430, 0 failures;
- idempotence replay: passed (`unchanged=true`);
- current catalog aggregates: 9,084 products, 7,061 site products, one product
  family, 264 site URLs and 253 site SEO rows; this evidence command changed none
  of those entity types.

## Readiness

The collision-classification substage is **100% complete**. Canonical identity
is deliberately not claimed for the 408 held members; the next bounded step is
primary-source verification of the 22 single-high-signal candidates, followed
by separate variant analysis for the 26 multi-signal groups.

