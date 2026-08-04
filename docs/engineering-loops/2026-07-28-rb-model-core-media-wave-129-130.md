# RB catalog loop — model-core media and FIAMM content (waves 129–130)

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`  
Fixed catalogue denominator: 7,286 products

## Outcome

- Audited 20 Bitrix↔1C legacy-media candidates. Literal identity gates retained 15; visual review retained 13; one motorcycle/starter battery was excluded from the current B2B scope. Twelve company-owned images were imported.
- The twelve linked products were published only as `noindex` preview cards. No offer, stock claim, indexable URL, or new price was created. One previously verified legacy price was retained.
- Added two FIAMM descriptions from the official FIAMM catalogue. The editorial pipeline changed no publication or commercial fields.
- Reclassified the Delta batch honestly: `delta-battery.ru` is an official dealer rather than the manufacturer. Fifty-one rows were applied only as explicitly labelled `dealer_backed` evidence; five rows remain excluded pending another source check.
- Added persistent source provenance to description drafts. Dealer evidence is restricted to exact brand+model text already present in the 1C name and may add only nominal voltage/capacity; it cannot establish or change canonical manufacturer/MPN/name or any commercial/media field.

## Adversarial gates

- A false APC SMT3000IC ↔ INELT GAMMA 3000VA relationship was caught before extraction/import.
- Two visually ambiguous images were rejected because the exact rating/model could not be read.
- `model_core` matching uses exact name boundaries and manufacturer agreement; it never writes a guessed MPN.
- Repeating the media apply returned `0 imported / 12 unchanged`, confirming idempotency.

## Verified counters

| Criterion | Count | Fixed-baseline coverage |
|---|---:|---:|
| Applied source-backed descriptions | 558 | 7.66% |
| Applied drafts explicitly classified `dealer_backed` | 51 | 0.70% |
| Storefront-ready verified images | 56 | 0.77% |
| Products with verified price | 57 | 0.78% |
| Strict content-complete cards | 56 | 0.77% |

Strict completeness requires a published preview, applied description, and verified published image. Therefore descriptions alone do not inflate the completion percentage.

## Verification

- Preview dry-run/apply: 12 products, 3 categories, 0 indexable URLs, 0 offers.
- Media dry-run/apply: 12/12 imported; idempotency rerun: 12/12 unchanged.
- Python tests: 13 passed.
- PHP regression tests: 19 passed, 100 assertions; focused dealer rerun: 2 passed, 18 assertions.
- `seo:audit microchips-by --json`: passed, 0 blocking issues across 131 checked URLs.
- Runtime: `/catalog` HTTP 200; `/contacts` HTTP 200.
- Docker: backend, worker, frontend, nginx, PostgreSQL, and Redis healthy.

## Next gate

Use series-level official catalogues and the classified dealer tier to fill descriptions in clusters, while prioritising exact image acquisition and visual matching. The strict completion score remains image-bound: the five Delta cache-miss rows stay on hold, and no description-only card is counted complete.
