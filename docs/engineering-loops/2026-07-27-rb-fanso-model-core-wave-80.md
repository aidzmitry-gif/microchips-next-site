# RB FANSO model-core enrichment wave 80 — 2026-07-27

## Result

- Applied official FANSO model-core descriptions and technical attributes to 27 RB catalogue products.
- Kept 18 ambiguous candidates blocked, including CR-series rows, ER models without the exact `H/M` suffix, and a suspicious `ER2450-VCY2` identity.
- Connector, terminal, lead, bundle, pack, compatibility, pulse-current and country claims remain outside the verified scope.
- No product was published and no price, stock or MPN was created.

## Verification

- Generator unit tests: 7/7; Python compile check: PASS.
- Stage dry-run: `27 created, 0 unchanged`; stage apply: `27 created, 0 unchanged`.
- Apply dry-run: `27 validated, 0 unchanged`; apply: `27 applied, 0 unchanged`.
- Database invariant check: 27/27 products found, 27/27 described, 27/27 technical-attribute sets, 27 applied drafts, 0 nonblank MPNs, 0 published products, 0 priced products.
- Manifest is strict UTF-8 with 27 unique external IDs and approved model-core fields only.
- Manifest SHA-256: `58FD4A054409A818129D188E80B7A27DE84F5C4F317F0C460D79C4694593C03E`.
- Queue was regenerated after the concurrent conservative taxonomy correction: 5,782 eligible products, 30 content-complete cards and 699 queue records; electronic components remain excluded.
- Final queue SHA-256 after taxonomy wave 85: `ECB4A18A19D6C73477AFB5DC15861375FFF408A707CE4B95E2DEC0ACE7282FC8`; UTF-8 BOM present, no Unicode replacement characters.
- SEO release audit after the taxonomy wave: PASS; 42 URLs and 0 blockers.

## Reproducible artifacts

- `scripts/build-fanso-model-core-description-manifest.py`
- `scripts/tests/test_build_fanso_model_core_description_manifest.py`
- `docs/imports/rb-source-backed-description-drafts-fanso-model-core-wave-80-2026-07-27.json`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.csv`
- `docs/audits/generated/rb-first-10-percent-enrichment-queue.summary.json`

## Progress accounting

The 27 cards now need verified media rather than both description and media. Because the strict readiness metric requires both assets, it remains `30 / 7,286 = 0.41%`; no +10-point milestone is claimed.
