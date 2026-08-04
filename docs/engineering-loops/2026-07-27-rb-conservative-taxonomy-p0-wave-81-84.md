# RB conservative taxonomy P0 waves 81-84 — 2026-07-27

## Result

- Applied 12 category-link corrections across 10 unpublished `microchips-by` site drafts.
- Excluded the unpublished service `КА-00003269` from `microchips-by`; the canonical product was not deleted.
- Moved the CSB survivor `КА-00001066` from `seo:rechargeable-cells` to `seo:batteries-ups`.
- Did not apply exclusion of `КА-00001750`: it is linked only to `microchips-ru`, while survivor `КА-00001066` is linked only to `microchips-by`. Removing the RU draft would leave that market without a survivor link.
- P1/P2 and `seo:electronic-components` were not touched.

## Safety gates

- Pre-apply guard: 11/11 requested RB site links existed, 11/11 were unpublished, 0 were published, and the CSB survivor existed.
- Wave 81 dry-run: 10/10 accepted; apply import run `438`: 10 moves, 0 errors.
- Wave 82 dry-run: 2/2 accepted; apply import run `440`: 2 moves, 0 errors.
- Wave 83 dry-run: 1/1 accepted; apply import run `441`: 1 excluded site draft, 0 canonical products deleted, 0 published products changed.
- Post-apply idempotence: wave 81 reported 10 already moved; wave 82 reported 2 already moved.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.
- Wave 84 mechanical dry-run passed for one unpublished `microchips-ru` draft, but the cross-market survivor guard blocked apply.

## Final category state

- `КА-00001066`, `КА-00001344`, `КА-00003848` → `seo:batteries-ups`
- `КА-00001497`, `КА-00002353` → `seo:rechargeable-cells`
- `КА-00001861` → `seo:primary-cells`
- `КА-00004782`, `КА-00004783` → `seo:batteries-traction`
- `КА-00004973` → `seo:printing-equipment`
- `ФР-00000453` → `seo:lighting-fixtures`

## Reproducible manifests

- `docs/imports/rb-site-category-move-wave-81-conservative-p0.csv`
- `docs/imports/rb-site-category-move-wave-82-conservative-p0-residual.csv`
- `docs/imports/rb-scope-exclusion-wave-83-service-installation.csv`
- `docs/imports/ru-strict-duplicate-exclusion-wave-84-csb-gp12170b1.csv` — dry-run only; blocked until the survivor has a `microchips-ru` site link.

Category manifests require `--category-source=full_catalog_seo_tree`; all commands remain dry-run unless `--apply` is supplied.
