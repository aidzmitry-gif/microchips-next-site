# Engineering readiness loop: +10 points

## Target and baseline

Start: 4.8% verified overall readiness. Target: at least 14.8% without changing Bitrix production, using production credentials or fabricating regional data.

The loop uses the agreed formula: `Σ(part weight × verified readiness) / 100`. A component receives points only after its stated evidence is produced. Missing external authority is marked `skipped`, not guessed.

## Cycle 1 — build in parallel

| Workstream | Owner | Acceptance evidence | Expected contribution |
| --- | --- | --- | ---: |
| Safe staging-to-review-to-publish catalogue flow | Catalog/import loop | PHPUnit proof that invalid or duplicate records cannot publish, and approved site-scoped records can publish | Part 3: functionality 40% + documentation 10% |
| SEO release gate | SEO QA loop | PHPUnit failures for cross-country canonical, non-reciprocal hreflang, redirect and sitemap errors; passing site audit command | Part 4: functionality 40% + validated sitemap/SEO 25% + documentation 10% |
| Repeatable quality gate | CI/operations loop | CI definition and a locally passing one-command quality gate | Evidence for the next CI execution; no CI points until a remote run passes |

## Cycle 2 — integration and review

1. Run the unified quality gate after all changes are integrated.
2. Run the SEO command against seeded site data and preserve its report.
3. Run the import workflow tests and check that no site publishes a product without explicit site review.
4. Inspect changed files for accidental credentials, copied Bitrix redirect rules, country leakage or invented commercial data.

## Cycle 3 — verified result

The integrated quality gate passed on 2026-07-14:

- PHP lint and Laravel Pint;
- PHPUnit: 13 tests, 67 assertions;
- Next.js 16.2.10 production build;
- `docker compose config`;
- `php artisan seo:audit microchips-by --json`: 1 indexable sitemap URL, 0 blocking issues.

| Part | Credited criteria | Readiness | Contribution |
| --- | --- | ---: | ---: |
| 3. Shared catalog and import core | Working functionality: the PHPUnit workflow proves invalid and duplicate staged records cannot publish, while an approved record creates a draft `site_product` with an audit trail. | 40% | 6.0 points |
| 4. Regional SEO/GEO | Working functionality: the release gate checks canonical, `hreflang`, sitemap and redirects. Data/SEO validation: a seeded Belarus profile passed the release audit with an indexable sitemap URL. | 65% | 6.5 points |

Verified total: **17.3%**, an increase of **12.5 percentage points** from the 4.8% baseline. This exceeds the +10 target.

The documentation/reproducible-deploy component was deliberately not credited: Docker was validated only with `compose config`, not with a running deployment. The tests-and-CI component was also not credited because the GitHub workflow has not had a remote passing run. No country-launch percentage changed.

## Explicitly skipped external tasks

- Connect and test a real Bitrix24 webhook.
- Validate a representative 1C export against business ownership rules.
- Start Docker Desktop or deploy a staging environment.
- Obtain an authenticated current-production crawl or Search Console/Yandex access.

Those items remain launch blockers, but do not pause this loop.
