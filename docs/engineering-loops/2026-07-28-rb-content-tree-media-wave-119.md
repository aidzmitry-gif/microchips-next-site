# RB content, tree and media — Wave 119

## Result

- Applied 28 new source-backed descriptions: 12 Robiton, 13 primary cells and
  3 industrial batteries. No product was automatically published and no
  price, stock or local warranty was inferred.
- Conflicting BAE, Leoch, Kijo, PKCELL and terminal/package variants remain on
  hold.
- Corrected the live category tree: removed 21 erroneous secondary links from
  stationary batteries while preserving their verified AGM category `410`.
- Excluded one non-public IGBT module from the RB market link. Canonical
  identity and other markets were not changed.
- Audited 276 current products without a category. Existing high-signal rules
  safely assigned none; all 276 remain hold instead of being forced into an
  incorrect SEO leaf.
- The only new exact media candidate, Tekcell CR123A-TC, failed machine vision
  because the model is not visible. No unsafe image was published.

## Live state after apply

| Metric | Value |
|---|---:|
| RB site products | 7 115 |
| Exactly one category | 6 839 |
| Multiple categories | 0 |
| No category / hold | 276 |
| Enrichment-eligible products | 5 698 |
| Strictly complete cards | 44 / 7 286 (0.60%) |
| New source-research clusters | 62 |
| SEO audit | 119 URLs, 0 blockers |

The strict card percentage did not increase because the 28 new descriptions
have no independently approved exact-model image. The source-research queue
decreased from 83 to 62 clusters without relaxing the media gate.

## Verification

- Three staging dry-runs: 12 + 13 + 3 created, 0 published.
- Three apply dry-runs: 28 validated, 0 commercial changes.
- Three applies: 28 descriptions applied, 0 publications.
- Redundant category removal dry-run: 21/21 valid and every product retains a
  category.
- Redundant category apply: 21 links removed, 0 products left uncategorized.
- PHP feature test: 1 passed, 5 assertions.
- Python batch tests: 6 passed.
- SEO audit: passed, 0 blocking issues.

## Main artifacts

- `docs/imports/rb-source-backed-description-drafts-robiton-wave-119-2026-07-28.json`
- `docs/imports/rb-source-backed-description-drafts-cells-wave-119-2026-07-28.json`
- `docs/imports/rb-source-backed-description-drafts-industrial-wave-119-2026-07-28.json`
- `docs/imports/rb-redundant-category-links-wave-119.csv`
- `docs/imports/rb-scope-exclusion-igbt-wave-119.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-119-final.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-119-final-summary.json`
- `docs/audits/2026-07-28-rb-tekcell-cr123a-media-hold-wave-119.md`
