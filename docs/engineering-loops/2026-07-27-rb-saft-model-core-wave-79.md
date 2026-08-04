# RB Saft model-core enrichment wave 79 — 2026-07-27

## Result

- Applied official Saft model-core descriptions and technical attributes to 50 RB catalogue products.
- Kept 2 ambiguous assemblies blocked: `2LS17500` and the four-cell `LSH20` assembly.
- Kept connector, terminal, lead, bundle, assembly-topology and country claims outside the verified scope.
- No product was published and no price, stock or MPN was created.

## Identity and source guards

- `identity_scope=model_core` requires an exact manufacturer and model-core match.
- Only the reviewed Saft suffixes `CNA`, `CNR`, `FL`, `FLE`, `E-STD`, `2PF`, `3PF`, and `4PF` are accepted after the model core.
- Lookalike Cyrillic/Latin characters are normalized; longer models such as `LSH200` remain blocked.
- Every row retains the exact official Saft source URL and the retrieval date.

## Verification

- Stage idempotence: `0 created, 50 unchanged`.
- Apply dry-run: `50 validated, 0 unchanged`.
- Apply: `50 applied, 0 unchanged`.
- Database invariant check: 50/50 products found, 50/50 described, 50/50 technical-attribute sets, 50 applied drafts, 0 nonblank MPNs, 0 published products.
- Matcher unit tests: 8/8; stage/apply feature tests: 10/10 with 46 assertions; Pint and PHP syntax checks: PASS.
- SEO release audit: PASS; 42 URLs, 0 redirects, 0 hreflang alternates.
- Queue regeneration: 5,783 eligible products, 30 content-complete cards, 699 remaining queue records toward the fixed 729-card target; `seo:electronic-components` remains excluded.
- Manifest SHA-256: `C334BF27DCCEF528534FA20617F2EDD3392432525C76B533FA5F8136703C3617`.
- Queue SHA-256: `F8CD47098A2F757BB45724E2A04CA06352FD7DEC51B1769747CB864F62CE51CD`; UTF-8 BOM present, no Unicode replacement characters.

## Reproducible artifacts

- `scripts/build-saft-model-core-description-manifest.py`
- `scripts/tests/test_build_saft_model_core_description_manifest.py`
- `docs/imports/rb-source-backed-description-drafts-saft-model-core-wave-79-2026-07-27.json`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.csv`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.summary.json`

## Progress accounting

This wave improves 50 incomplete cards from two missing content assets to one, but verified content-complete readiness still requires both an applied description and storefront-ready verified media. The fixed-baseline metric therefore remains `30 / 7,286 = 0.41%`; no artificial +10-point milestone is claimed.
