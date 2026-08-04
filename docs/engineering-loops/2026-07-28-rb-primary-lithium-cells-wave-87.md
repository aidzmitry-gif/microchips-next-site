# RB primary lithium cells wave 87 — 2026-07-28

## Result

- Moved 16 explicit primary lithium-cell drafts from `seo:rechargeable-cells` to `seo:primary-cells` on `microchips-by`.
- The bounded wave contains nine SAFT LS14500 variants and seven PKCELL ER-series variants.
- Preserved every product identity, terminal, connector and OEM/packaging variant; no deduplication or exclusions were performed.
- `КА-00005172` (`OEM LS33600-3 - 4`) was deliberately left unchanged because its target between primary cells and an industrial/OEM assembly category is not unambiguous from 1C.
- `seo:electronic-components` was not touched.

## Safety gates

- Candidate review: 17 RB/1C rows inspected; 16 accepted and one ambiguous OEM assembly deferred.
- Manifest: 16 rows and 16 unique product IDs.
- Pre-apply guard: 16/16 products, RB links and non-group 1C items existed; all 16 RB links were unpublished; all 16 were assigned to rechargeable cells; 0 already had the primary target; 0 had electronic-components links.
- Strict duplicate scan: 0/16 IDs occurred in `docs/audits/generated/one-c-strict-duplicate-candidates.csv`.
- Dry-run import `452`: 16 moves accepted, 0 validation errors.
- Apply import `453`: 16 moves completed, 0 already moved, 0 publication changes.
- Idempotence import `454`: 0 pending moves, 16 already moved.
- Post-apply guard: 16/16 RB links and 1C items remained; 16/16 were in primary; 0 remained in rechargeable; 0 were published; 0 had electronic-components links.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.

## Preserved variants

- SAFT LS14500: bare, `ER6VC119B`, `ER6V`, `ER6C F2-40BL`, `2PF`, `3PF`, `R88A-BAT01G` and `FLE` wording variants.
- PKCELL ER14505: bare, 2510-2P and JST ENR-2P connector variants.
- PKCELL ER34615: bare and Molex 2510-2 variants.
- PKCELL ER18505 XHR-2P and ER26500 Dubon 2P variants.

## Post-wave category counts

- `seo:primary-cells`: 1,380
- `seo:rechargeable-cells`: 2,588

## Reproducible manifest

- `docs/imports/rb-site-category-move-wave-87-primary-lithium-cells.csv`

The category command requires `--category-source=full_catalog_seo_tree`; it remains dry-run unless `--apply` is supplied.
