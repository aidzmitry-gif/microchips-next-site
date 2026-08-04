# RB PKCELL model-core enrichment wave 82 — 2026-07-28

## Result

- Applied official PKCELL `R03`/AAA Ni-MH model-core facts to 4 RB catalogue products.
- Kept 5 `R06`/AA rows blocked because their 2,800 mAh claim exceeds the current official PKCELL range of 350–2,700 mAh.
- The first generated manifest was correctly rejected by Laravel because its synthetic model core was absent from the product name. The generator was corrected without weakening the global matcher.
- Every accepted row now requires exact `R03` boundaries together with explicit `PKCELL` and `Ni-MH` evidence.
- Pack voltage, number of cells, RTU, retail package and execution details remain unverified.
- No product was published and no price, stock or MPN was created.

## Verification

- Generator tests: 8/8; Python compile and manifest assertions: PASS.
- Initial fail-closed check: rejected synthetic `PKCELL-AAA-NIMH` identity as expected.
- Corrected stage dry-run: `4 created, 0 unchanged`; stage apply: `4 created, 0 unchanged`.
- Apply dry-run: `4 validated, 0 unchanged`; apply: `4 applied, 0 unchanged`.
- Database invariant check: 4/4 products found, 4/4 described, 4/4 technical-attribute sets, 4 applied drafts, 0 nonblank MPNs, 0 published products, 0 priced products.
- Manifest SHA-256: `029DE54CE1A3E76573F89D54E756F32A0EAE6EB90808349BB1179579D5417863`.

## Reproducible artifacts

- `scripts/build-pkcell-model-core-description-manifest.py`
- `scripts/tests/test_build_pkcell_model_core_description_manifest.py`
- `docs/imports/rb-source-backed-description-drafts-pkcell-model-core-wave-82-2026-07-28.json`

## Progress accounting

These four cards now have verified descriptions but still need rights-cleared, visually verified media. They improve catalogue depth without increasing the strict content-complete count yet.
