# RB battery holders/accessories wave 86 — 2026-07-27

## Result

- Moved 11 explicit battery holders/cases from `seo:primary-cells` or `seo:rechargeable-cells` to `seo:batteries-accessories` on `microchips-by`.
- Preserved all 11 product identities without deduplication.
- Preserved CR2032/CR2450, BS/BS-3, 1S1P/1S2P/1S3P and wired-holder variants as separate cards.
- No products were published or excluded; P1 scope was category links only.
- `seo:electronic-components` was not touched.

## Safety gates

- Manifest: 11 rows and 11 unique product IDs.
- Pre-apply guard: 11/11 products, RB links and non-group 1C items existed; 11/11 RB links were unpublished; all 11 had the expected wrong source category; 0 already had the target category; 0 had an electronic-components link.
- Strict duplicate scan: 0/11 IDs occurred in `docs/audits/generated/one-c-strict-duplicate-candidates.csv`. This check was informational because no identities were merged or removed.
- Dry-run import `449`: 11 moves accepted, 0 validation errors.
- Apply import `450`: 11 moves completed, 0 already moved, 0 publication changes.
- Idempotence import `451`: 0 pending moves, 11 already moved.
- Post-apply guard: 11/11 RB links and 1C items remained, 11/11 were in accessories, 0 remained in the wrong source categories, 0 were published, 0 had electronic-components links.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.

## Preserved variants

- BS for CR2032: `КА-00000009`
- BS for CR2450: `КА-00000010`, `КА-00000468`
- BS-3 for CR2032: `ФР-00000018`, `ФР-00000257`, `ФР-00000803`
- 18650 1S2P / 1S3P / 1S1P: `КА-00000487`, `КА-00000488`, `КА-00000489`, `ФР-00001064`
- Wired single holder: `ФР-00000876`

## Post-wave category counts

- `seo:batteries-accessories`: 16
- `seo:primary-cells`: 1,364
- `seo:rechargeable-cells`: 2,604

## Reproducible manifest

- `docs/imports/rb-site-category-move-wave-86-battery-holders-accessories.csv`

The category command requires `--category-source=full_catalog_seo_tree`; it remains dry-run unless `--apply` is supplied.
