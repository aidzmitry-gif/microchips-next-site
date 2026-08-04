# RB SAFT/FANSO/TEKCELL dedup waves 76-78 — 2026-07-27

## Result

- Reviewed 148 enrichment candidates against their full 1C and Bitrix context.
- Excluded 27 exact model/terminal/connector/packaging duplicates from the RB site profile.
- Canonical shared products were not deleted and other market profiles were not changed.
- Corrected 11 canonical survivors from `seo:warehouse-equipment` to `seo:primary-cells` before removing their duplicates.
- Electronic components were not touched.

## Safety gates

- Every excluded RB link was unpublished.
- Wave 76 dry-run validated 12/12 records before apply.
- Wave 77 dry-run validated 11/11 category moves before apply.
- Wave 78 dry-run validated 15/15 records before apply.
- Category move idempotence: 0 pending, 11 already moved.
- SEO audit after apply: PASS, 42 URLs, 0 redirect errors.
- Eligible non-electronic RB catalogue records changed from 5,810 to 5,783 exactly as expected (`-27`).

## Preserved variants

Connector, terminal, pack-size, OEM and battery-assembly variants were deliberately kept separate. Ambiguous pairs such as SAFT JST variants, BAT08 OEM references, FANSO `ENR-2` vs `EHR-2`, unspecified lead variants, and TEKCELL rows without a proven connector were not auto-merged.

## Reproducible manifests

- `docs/imports/rb-strict-duplicate-exclusion-wave-76-saft-fanso-tekcell.csv`
- `docs/imports/rb-site-category-move-wave-77-primary-cell-survivors.csv`
- `docs/imports/rb-strict-duplicate-exclusion-wave-78-saft-fanso-tekcell.csv`
