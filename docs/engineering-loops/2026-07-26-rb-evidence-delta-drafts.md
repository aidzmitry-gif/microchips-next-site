# RB: evidence-backed catalog delta — non-public drafts

Date: 2026-07-26.

## Scope

Three evidence packets selected 27 exact identity decisions. No identifier was inferred from a product name or warehouse code.

## Controlled execution

1. Applied the three versioned evidence files in `docs/imports/` through `catalog:apply-identity-review-evidence`.
2. Exported only their approved candidate IDs as explicit deltas, then staged them as import runs **25**, **26** and **27**.
3. The staging results were **15**, **5** and **7** ready records respectively, with **0 duplicate conflicts** in every run.
4. Used the bounded `catalog:review-publish-staged-delta` command with the matching expected count for every run.

The command rejects a non-dedicated run, requires the exact expected count, uses the normal review and identity guards, and only creates `SiteProduct` records with `is_published=false`.

## Result

| Check | Result |
| --- | ---: |
| Evidence-backed identity decisions applied | 27 |
| Approved identity candidates total | 50 |
| Pending candidates | 58 |
| Rejected candidates | 1 |
| Records published into drafts (runs 25–27) | 27 |
| RB drafts total | 50 |
| Public RB product cards after the operation | 0 |
| Cross-candidate SKU/MPN conflicts in the three deltas | 0 |

This is a catalog-preparation result, not a launch or SEO-release result. The products have no prices, availability promises, descriptions, images, or public URLs. Site-category assignment is deliberately deferred: the current RB taxonomy is still an unpublished three-node pilot tree and must be extended from the verified source taxonomy rather than from product names.

## Regression safety

`catalog:review-publish-staged-delta` has a feature test for the exact-count fail-closed guard, dry-run behavior, and non-public publication. PHP syntax validation and a production-container dry-run were completed before applying run 25.

## Next safe action

Research and import authoritative chemistry/category evidence for the next controlled delta. Do not use search snippets or names alone to assign a product to the published taxonomy.
