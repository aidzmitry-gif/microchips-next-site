# RB catalogue loop — row-level link gate and bulk preview (waves 132–133)

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`  
Fixed catalogue denominator: 7,286 products

## Outcome

- Corrected an over-broad Bitrix↔1C safeguard. `rb-1c-review-exclusions.csv` contains rejected relationship rows, but the previous media queue treated every referenced 1C product as globally excluded. A valid exact relationship could therefore be blocked by unrelated generic candidates for the same product.
- Product-level scope and duplicate decisions remain hard exclusions. Review-row exclusions are now evaluated per relationship: a media candidate still requires a unique current brand+model identity, literal brand/model agreement in the legacy name, a single trusted strict relationship and a legacy ID owned by only one 1C product.
- Rebuilt the queue against 66 already verified media products and all prior visual verdicts. The corrected gate produced 16 new candidates; all 16 company-owned archive assets were extracted and visually reviewed.
- Visual review retained 11 and rejected 5. The rejected images had unreadable identity/rating or a visible contradiction, including 20 Ah versus 21 Ah and HRL12550W versus HRL12650W.
- Published 11 source-backed products as `noindex` previews and imported 11 verified images. The immediate second media apply returned `0 imported / 11 unchanged`.
- Added a separate bulk source-backed preview builder. It published all 211 unique, in-scope, single-category products with applied evidence as `noindex`; 114 were already published and 97 became newly visible. Twenty-seven rows retained only matching current price provenance.

## Duplicate audit

The 289 rows initially labelled `duplicate_current_brand_model_identity` were not auto-merged. Adversarial grouping across every applied peer found that almost all are material variants or incomplete identities: terminal, pack, voltage/capacity and connector differences are common. No image reuse or duplicate exclusion was authorised from brand+model equality alone.

## Fail-closed bulk preview rules

- only products present on the RB site and in one allowed battery/power category;
- electronic components remain excluded;
- one unique canonical brand+model/MPN identity across every applied peer;
- exact brand and identity boundaries already present in the 1C name;
- HTTPS source URL already attached to an applied description;
- all evidence-backed scope/duplicate loser manifests honoured;
- unique product slug;
- `noindex` URL and SEO record only; no stock assertion or offer;
- a price is allowed only when the existing price-evidence gate confirms the current value.

## Verified counters after apply

| Criterion | Count | Fixed-baseline coverage |
|---|---:|---:|
| Applied source-backed descriptions | 558 | 7.66% |
| Visible published noindex products | 232 | 3.18% |
| Storefront-ready verified images | 77 | 1.06% |
| Products with verified price evidence | 57 | 0.78% |
| Strict content-complete cards | 77 | 1.06% |
| Indexable product URLs | 0 | 0.00% |

Strict completeness remains 77 because a card needs an applied description, a published preview and a verified published image. The extra noindex previews improve catalogue usefulness without inflating the SEO-ready counter.

## Verification

- Row-gate builder regression: 4 passed.
- Bulk-preview builder regression: 2 passed.
- Preview dry-run/apply: 211 products, 11 categories, 27 verified-priced products, 0 indexable URLs, 0 offers.
- Media dry-run/apply: 11/11 imported; idempotency rerun: 11/11 unchanged.
- `seo:audit microchips-by --json`: passed, 0 blockers across 261 checked URLs.
- Runtime: `/catalog` HTTP 200; `/contacts` HTTP 200.
- Docker services remained healthy during the cycle.

## Next gate

Use the same cluster pipeline for new manufacturer-series descriptions, starting with coherent exact families that have direct product sources. Media remains a separate visual/rights gate. Material variants remain separate products until terminal, pack and electrical signatures prove a true duplicate.
