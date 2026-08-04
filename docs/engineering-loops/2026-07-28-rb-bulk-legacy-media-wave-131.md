# RB catalogue loop — bulk legacy media (wave 131)

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`  
Fixed catalogue denominator: 7,286 products

## Outcome

- Rebuilt the legacy-media queue from the fresh applied-description, site-product, Bitrix, strict-link and existing-media states. Previously reviewed media and every explicit scope/duplicate exclusion are part of the input gate, so rejected work is not repeated.
- 558 applied descriptions produced 538 stable-evidence rows. The fail-closed classifier retained 14 new company-owned Bitrix images for visual review and rejected 544 rows before import.
- Parallel visual review covered all 14 assets: 10 passed visible exact model/rating checks; 4 were rejected because the identity or material rating was unreadable or contradictory.
- Published the 10 passed products only as regional `noindex` previews. No offer, stock assertion, indexable URL or unverified price was created.
- Imported 10 verified images. The immediate second apply returned `0 imported / 10 unchanged`, proving idempotency.

## Source and identity protection

- Preview publication now loads the exact applied description evidence instead of checking only that one exists.
- Dealer-backed evidence is restricted to `model_core`. It cannot establish an exact MPN or fill a blank canonical manufacturer.
- A dealer-backed manufacturer must already occur in the 1C product name with exact boundaries; a conflicting canonical manufacturer remains a hard blocker.
- The legacy-media importer follows the same rule: a blank canonical manufacturer may be checked against the 1C name but is never written from the media manifest.
- The manifest builder accepts both `exact` and `model_core` identities, supports the current nested site-state export and emits the matching evidence level.

## Queue evidence

| Stage | Count |
|---|---:|
| Applied description products | 558 |
| Stable evidence rows | 538 |
| Existing storefront media excluded | 56 |
| Previously reviewed media IDs excluded | 15 |
| Explicit scope/duplicate IDs excluded | 1,243 |
| New visual candidates | 14 |
| Visual PASS | 10 |
| Visual REJECT | 4 |

The largest retained blocker is not image extraction: 289 rows belong to duplicate current brand+model identities. They must be resolved as canonical product/variant clusters before the media gate can safely reuse an image.

## Verified counters after apply

| Criterion | Count | Fixed-baseline coverage |
|---|---:|---:|
| Applied source-backed descriptions | 558 | 7.66% |
| Storefront-ready verified images | 66 | 0.91% |
| Products with verified price evidence | 57 | 0.78% |
| Strict content-complete cards | 66 | 0.91% |
| Published noindex preview products | 124 | 1.70% |

Strict completeness requires a published preview, an applied description and a verified published image. Description-only pages do not increase this counter.

## Verification

- Preview dry-run: 10 products, 2 categories, 0 indexable URLs, 0 offers.
- Media dry-run/apply: 10/10 imported; idempotency rerun: 10/10 unchanged.
- Python regression: 6 passed.
- PHP regression: 36 passed, 187 assertions.
- `seo:audit microchips-by --json`: passed, 0 blockers across 141 checked URLs.
- Runtime: `/catalog` HTTP 200; `/contacts` HTTP 200.
- Docker: backend, worker, frontend, nginx, PostgreSQL and Redis healthy.

## Next high-throughput gate

Resolve the 289 duplicate brand+model rows into canonical products and explicitly preserved variants. Only exact duplicates may be excluded automatically; pack size, terminal, voltage, capacity and other material variants remain separate. The resolved canonical rows then re-enter the existing description/media pipeline in bulk without weakening the visual or source gates.
