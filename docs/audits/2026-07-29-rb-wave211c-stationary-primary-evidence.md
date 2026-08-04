# RB Wave211-C — stationary battery primary-source gate

Date: 2026-07-29  
Input: `rb-b2b-next-source-batch-wave210.csv`, exactly 129 rows: Sonnenschein 40, Yuasa 23, Panasonic 15, MNB 24, Sprinter 10, WBR 16, EnerSys 1.

## Outcome

Only SHA-pinned official manufacturer catalogues were accepted. The output is fail-closed: 50 `exact_safe`, one `conflict`, and 78 `no_evidence` rows.

| Partition | Rows |
| --- | ---: |
| exact_safe | 50 |
| conflict | 1 |
| no_evidence | 78 |

The lone conflict is `bitrix:2938`: its source-backed MPN is `MM 28-12`, but the legacy title uses a Cyrillic homoglyph, which the bounded Laravel name matcher correctly rejects. No global matcher was changed.

Yuasa, Sprinter and WBR remain `no_evidence`: no SHA-pinned official manufacturer-primary exact-model source was available. The single generic EnerSys Cyclon cell format is also not promoted because it does not prove a unique saleable MPN.

## Guards and verification

- Previous evidence-wave overlap: 0 IDs.
- Automotive/electronics scope gate: 0 rows.
- Full canonical registry collision guard: exact model extraction, no false prefix/variant collisions.
- Read-only live PostgreSQL collision guard: 0 collisions; 0 mutations.
- Laravel `catalog:apply-verified-oem-identities` ran without `--apply`: exit 0, 50 records, no commercial/publication changes; a second read-only query confirmed 0 rows gained manufacturer or MPN.
- Independent test rerun: **3 passed**. Import run **935** then filled all
  50 exact-safe identities; the idempotence rerun returned `0 filled / 50
  unchanged`. Commercial and publication changes remained **0**.
- Final SEO audit: **16,853 URLs, 97 redirects, 0 blockers**.

```text
python -m pytest scripts/tests/test_build_rb_wave211c_stationary_evidence.py -q -p no:cacheprovider
```

Key outputs: `rb-wave211c-stationary-evidence.csv`, `wave211c-stationary-live-identity-collisions.json`, `wave211c-stationary-laravel-dry-run.json`, and the 50-row OEM identity manifest.
