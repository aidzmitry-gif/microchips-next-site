# RB Delta / Fiamm / Leoch evidence — Wave209-B

## Result

The bounded Wave209-B scope contains 136 B2B industrial battery candidates:
Delta 80, Fiamm 33 and Leoch 23. There is no overlap with any Wave206 evidence
CSV. The explicit automotive/starter detector excluded zero rows; its separate
artifact is retained so a future batch cannot silently widen the scope.

Evidence partition after pinned-source and identity checks:

- `exact`: 20 Delta rows backed by SHA-256-pinned DELTA Battery product pages;
- `conflict`: 2 Delta rows (`HR 12-40`: official 45 Ah vs legacy 40 Ah;
  `HRL 12-26 X`: official 28 Ah vs legacy 26 Ah);
- `no_evidence`: 114 rows.

Fiamm rows remain fail-closed because the local pinned pages are from the
official distributor rather than a manufacturer-primary source. Leoch FT/DJW/DJM
rows remain fail-closed because the evidence store has no pinned exact-model
manufacturer page/PDF for this batch. Neither source class is promoted into the
manifest merely because a model name appears plausible.

## Duplicate and scope guards

All 20 exact candidates were checked against the complete 17,207-row canonical
registry and current Docker PostgreSQL `sku_normalized` / `mpn_normalized`
values. The live query returned 17 self rows (three candidates currently have
blank live identity) and no collision with another product. The exact-safe
manifest therefore contains 20 Delta rows.

## Verification

- Builder: `python scripts/build-rb-wave209b-delta-fiamm-leoch-evidence.py`
- Tests: `python -m pytest scripts/tests/test_wave209b_delta_fiamm_leoch_evidence.py`
- Laravel: `catalog:apply-verified-oem-identities` dry-run, 20 records, exit 0
- Independent test rerun: **4 passed**.
- Import run **930** applied the unchanged manifest: **3 identities filled / 17
  already identical**.
- Idempotence rerun: **0 filled / 20 unchanged**.
- Price, availability and publication fields changed: **0**.

Generated evidence, exclusions, collision proof, summary and dry-run proof are
under `docs/audits/generated/`. The only import artifact is
`docs/imports/rb-verified-oem-identities-wave209b-delta-2026-07-29.json`.
