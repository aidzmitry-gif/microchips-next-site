# Engineering loop: SEO migration registry (+10 points)

## Target and boundaries

Start: **22.8%** verified overall readiness. Target: at least **32.8%** without access to 1C, Bitrix24, Search Console, Yandex Webmaster or the production server.

The loop improves only Part 2, `Source audit and SEO registry` (weight 13%). A public crawl is read-only. It must not send forms, authenticate, mutate Bitrix data or bypass crawl controls.

If all objective gates pass, Part 2 reaches 90% and the verified total becomes **34.5%** (+11.7 points). The remaining 10% of Part 2 stays uncredited: a reproducible preview/staging migration is not available.

## Scoring contract

| Part 2 criterion | Evidence required | Readiness | Overall contribution |
| --- | --- | ---: | ---: |
| Working registry | A deterministic generator emits a row for every distinct source URL with `decision`, `review_status`, evidence and no invented destination. | 40% | +5.2 points |
| Tests and CI | Regression tests reject unsafe decisions and GitHub Actions passes for the implementation commit. | 25% | +3.25 points |
| Data / SEO validation | A read-only public crawl is captured, compared with the source inventory and validates all priority URL patterns. | 25% | +3.25 points |
| Documentation / reproducible deploy | Not in scope: there is no migration preview deployment. | 0% | +0 points |

`decision` is always one of `keep`, `fix`, `redirect` or `remove`. `review_status` is separate: `approved`, `needs_review` or `blocked`. A `needs_review` or `blocked` priority URL prevents release; it never becomes an unreviewed redirect.

## Cycle 1 — independent evidence

1. Capture a public, read-only sample of `robots.txt`, sitemaps and representative product, category, filter, article and utility URLs.
2. Compare its HTTP/SEO signals with the 2026-06-23 Bitrix snapshot and record observable drift and crawl limitations.
3. Build a local decision registry from `legacy-url-inventory.csv` and legacy redirect sources. Raw inventories remain ignored; only deterministic tooling and aggregate summaries are versioned.

## Cycle 2 — safety gates

1. Add a migration decision auditor with an explicit row contract.
2. Block redirect chains, homepage fallbacks, external or cross-country destinations, cross-country canonical URLs, `remove` decisions returning `200`, and unreviewed priority URLs.
3. Run the full local quality gate.

## Cycle 3 — remote proof and score

1. Publish the isolated implementation in a branch and run the existing GitHub Actions quality gate.
2. Inspect the public-crawl report and generated registry summary; no score is awarded for an incomplete or fabricated crawl.
3. Merge only a green, reviewed change; then record the exact Part 2 readiness and overall formula in `docs/implementation-status.md`.

## Release blockers preserved

- A legacy URL may not redirect to the homepage merely to avoid `404`.
- Filter, sort, search and tracking parameter URLs may not become indexable by accident.
- A `remove` record requires an intentional 404/410 response, never an accidental `200`.
- Commercial, legal or regional facts are not inferred from a URL, crawler output or the old Bitrix copy.
- The registry does not publish redirects; final destinations are allowed only after the shared catalogue has a matching approved site URL.
