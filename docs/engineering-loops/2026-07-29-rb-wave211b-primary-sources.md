# RB Wave211-B — primary-source identity gate

Date: 2026-07-29  
Scope: `rb-b2b-next-source-batch-wave210.csv`, exactly 158 source rows: Delta 66, Fiamm 43, Leoch 27 and CSB 22.

## Outcome

The batch is fail-closed. Eighteen Delta IDs already covered by earlier evidence waves were excluded before source review. The two Cardioline/ECG rows are medical battery assemblies, not electronic components: they remain in the catalogue evidence scope as fail-closed specialist/OEM-device holds. The resulting eligible scope is 140 rows.

| Partition | Rows |
|---|---:|
| `exact` | 1 |
| `conflict` | 17 |
| `no_evidence` | 122 |

Only `bitrix:3212` (Delta DT 1275) reached the exact-safe manifest. The 17 remaining Delta pages were SHA-pinned first-party pages but are held by the full-catalog and live PostgreSQL collision guards (one row also has a 9 Ah vs 8.8 Ah title conflict). `bitrix:11255` and `bitrix:11257` remain `no_evidence` pending a medical specialist/OEM device source; they do not enter the Delta stationary-battery acquisition or manifest. Fiamm's local material is distributor evidence and is not promotable; no exact pinned manufacturer-primary pages are available for the remaining Fiamm, Leoch or CSB candidates.

## Guards and dry-run

- Full canonical registry collision guard: enabled for every exact primary candidate.
- Read-only live PostgreSQL guard: checked 18 exact Delta MPNs; 17 collision candidates were held.
- Laravel `catalog:apply-verified-oem-identities` ran without `--apply` against the final one-row manifest: exit 0, no commercial or publication fields changed, database mutations 0.
- Independent test rerun: **3 passed**. Import run **934** then filled the
  single verified identity; the idempotence rerun returned `0 filled / 1
  unchanged`. Commercial and publication changes remained **0**.

## Verification

```text
python scripts/build-rb-wave211b-primary-evidence.py --provisional
python -m pytest scripts/tests/test_build_rb_wave211b_primary_evidence.py -q -p no:cacheprovider
# 3 passed
```

Key artefacts:

- `docs/audits/generated/rb-wave211b-delta-fiamm-leoch-csb-evidence.csv`
- `docs/audits/generated/wave211b-live-identity-collisions.json`
- `docs/audits/generated/wave211b-laravel-dry-run.json`
- `docs/imports/rb-verified-oem-identities-wave211b-delta-2026-07-29.json`
