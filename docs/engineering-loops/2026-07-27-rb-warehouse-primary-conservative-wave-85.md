# RB warehouse → primary conservative wave 85 — 2026-07-27

## Result

- Moved 45 explicit consumer primary-cell drafts from `seo:warehouse-equipment` to `seo:primary-cells` on `microchips-by`.
- Preserved every product identity and packaging variant; the wave changed category links only.
- No site products were published or excluded.
- P1 and `seo:electronic-components` were not touched.

## Safety gates

- Manifest: 45 rows, 45 unique product IDs, one source category and one target category.
- Pre-apply DB guard: 45/45 products and RB links existed, 45/45 were unpublished, 45/45 were assigned to warehouse, 0 were already assigned to primary.
- Strict duplicate guard: 0/45 IDs occurred in `docs/audits/generated/one-c-strict-duplicate-candidates.csv`.
- Dry-run import `445`: 45 moves accepted, 0 validation errors.
- Apply import `446`: 45 moves completed, 0 already moved, 0 publication changes.
- Idempotence import `447`: 0 pending moves, 45 already moved.
- Post-apply DB guard: 45/45 remained linked and unpublished, 45/45 in primary, 0/45 in warehouse.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.

## Post-wave category counts

- `seo:primary-cells`: 1,370
- `seo:warehouse-equipment`: 591

## Reproducible manifest

- `docs/imports/rb-site-category-move-wave-85-warehouse-primary-conservative.csv`

The category command requires `--category-source=full_catalog_seo_tree`; it remains dry-run unless `--apply` is supplied.
