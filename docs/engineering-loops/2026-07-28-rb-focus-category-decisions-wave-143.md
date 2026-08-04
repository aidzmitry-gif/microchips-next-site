# RB focus category decisions — wave 143

## Outcome

The 219 source-descendant rows now have a complete, reproducible and
non-releasing focus decision manifest. The database also has boundary root 372
(`akkumulyatory`), so the final hierarchy audit covers 220 rows. This closes the
missing category-level evidence gap without repeating the existing 489-path
full-catalog taxonomy audit.

| Decision | Categories |
|---|---:|
| `focus_populated` | 10 |
| `empty_in_focus_preview` | 206 |
| `empty_duplicate_candidate` | 3 |
| release allowed | 0 |

The hierarchy-aware 220-row result is: 10 `keep_candidate`, 206
`empty_in_focus_preview`, three `merge_duplicate` and one `hold`. Root 372 is a
keep candidate. Category 425 (`istochniki-pitaniya/ibp`, 337 products) is held
because its intended parent path is absent from the registry; it must stay
visible as a temporary held root rather than being silently attached elsewhere.

The snapshot contains 1,569 records. The noindex preview correctly exposes
1,562 in-scope records and excludes six inactive legacy records plus one
electronics record. Therefore active focus counts can be lower than counts in
the unfiltered 1,569-record audit.

## Important safety correction

Zero members inside the selected RB B2B focus does not prove that a legacy
category is globally empty. The 206 zero-focus categories are therefore marked
`empty_in_focus_preview`, not delete, redirect or merge.

Only three numeric-suffix branches are recorded as duplicate candidates, still
without mutation:

- 1125 `dlya_ibp9002` -> 409 `dlya_ibp`;
- 1123 `promyshlennye7593` -> 427 `promyshlennye`;
- 1135 `ibp483` -> 425 `ibp`.

URL traffic, content intent and canonical taxonomy must be checked before any
redirect or merge is emitted.

There is also one unresolved primary path:
`akkumulyatornye-batareyki/lifepo4` affects 43 staged rows. All 43 retain valid
matched-category memberships and remain discoverable, but this missing primary
category must not be synthesized automatically.

## Populated focus branches

The visible preview evidence contains ten populated branches: AGM 933, UPS 337,
telecommunications 326, alarm systems 283, reserve power 197, GEL 144,
industrial batteries 70, medical equipment 70, OPzS 16 and batteries for UPS 3.
Membership counts overlap because a product may have multiple Bitrix section
memberships; they must not be summed as a product total.

## Duplicate guard

The 430 rows previously labelled `candidate_duplicate_group` are 88 mapping
collision groups, not 430 proven duplicates. Evidence review split:

- 306 non-strict members remain `hold_insufficient_identity_evidence`;
- 40 groups have no high-signal member and remain collision holds;
- 22 groups have one high-signal candidate and form the first review queue;
- 26 groups have multiple high-signal candidates and remain variant/collision
  holds.

No product, family, site link, publication, URL, SEO record or media row was
created, merged or removed by this wave.

## Artifacts and verification

- `scripts/build-bitrix-to-seo-category-evidence.py`
- `scripts/tests/test_build_bitrix_to_seo_category_evidence.py`
- `docs/audits/generated/rb-bitrix-to-seo-category-evidence-wave143.csv`
- `docs/audits/generated/rb-bitrix-to-seo-category-evidence-wave143-summary.json`

Verification:

- Python compile: passed;
- focused pytest: 2 passed;
- expected inputs: 219 categories and 1,569 records;
- manifest output: exactly 219 rows;
- all `release_allowed=false`;
- source SHA-256 hashes recorded in the summary.

## Readiness

- Safe Bitrix transfer/preview stream: **90%** (unchanged; category decision gap
  is now closed, but URL/traffic decisions and duplicate identity review remain).
- Strict canonical RB catalog: **77 / 7,286 = 1.06%** (unchanged; no readiness is
  claimed from evidence-only work).
