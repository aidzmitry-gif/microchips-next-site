# RB UPS and traction battery taxonomy wave 89 — 2026-07-28

## Result

- Moved 17 explicit specialised battery drafts out of `seo:rechargeable-cells` on `microchips-by`.
- Moved 13 APC RBC/SURT replacement battery or battery-kit variants to `seo:batteries-ups`.
- Moved four batteries with explicit PzS or named forklift application (`TOYOTA 8FBET15`, `JUNGHEINRICH EFG 215`, `BT RRE 120M`) to `seo:batteries-traction`.
- Preserved every identity, model, kit and capacity variant; no deduplication or exclusions were performed.
- `seo:electronic-components` was not touched.

## Adversarial review

- Audited remaining unpublished RB rows in both `seo:warehouse-equipment` and `seo:rechargeable-cells` against 1C names and paths.
- The warehouse primary-keyword scan returned 181 mixed rows, including true primary cells but also Ni-MH/18650 products and dense packaging/terminal variants. It was not mixed into this bounded wave.
- Generic AGM/GEL/lead-acid rows were not automatically classified as UPS or traction because many can serve industrial, standby, mobility or other applications.
- Accepted only APC replacement-battery model families and traction rows with explicit PzS or named forklift evidence.

## Safety gates

- Manifest: 17 rows and 17 unique product IDs; 13 UPS targets and four traction targets.
- Pre-apply guard: 17/17 products, RB links and non-group 1C items existed; all 17 RB links were unpublished; all 17 were assigned to rechargeable cells; 0 already had its target; 0 had electronic-components links.
- Strict duplicate scan: 0/17 IDs occurred in `docs/audits/generated/one-c-strict-duplicate-candidates.csv`.
- Dry-run import `463`: 17 moves accepted, 0 validation errors.
- Apply import `464`: 17 moves completed, 0 already moved, 0 publication changes.
- Idempotence import `465`: 0 pending moves, 17 already moved.
- Post-apply guard: 17/17 RB links and 1C items remained; 17/17 were in the intended target; 0 remained in rechargeable; 0 were published; 0 had electronic-components links.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.

## Post-wave category counts

- `seo:batteries-ups`: 81
- `seo:batteries-traction`: 37
- `seo:rechargeable-cells`: 2,541
- `seo:warehouse-equipment`: 591

## Reproducible manifest

- `docs/imports/rb-site-category-move-wave-89-ups-traction-batteries.csv`

The category command requires `--category-source=full_catalog_seo_tree`; it remains dry-run unless `--apply` is supplied.
