# Wave209-C — stationary batteries: primary-source identity evidence

Checked: 2026-07-29. Scope is exactly 81 new Bitrix cards from
`rb-b2b-next-source-batch-wave208.csv`: B.B. Battery 11, CSB 9, Casil 3,
Panasonic 3, Robiton 2, Sprinter 6, Ventura 25, WBR 10, and Yuasa 12.

The Wave206 and Wave208-S evidence IDs were loaded before selection; the
intersection is empty. Automotive and electronics exclusions are both zero.

## Evidence decision

| Partition | Cards | Rule |
| --- | ---: | --- |
| `exact_safe` | 12 | Exact model appears in a SHA-pinned primary snapshot and neither full registry nor live PostgreSQL reports an identity collision. |
| `conflict` | 14 | Exact primary evidence exists, but a registry or live PostgreSQL collision requires review. |
| `no_evidence` | 55 | No pinned primary source proves the exact offered model; no identity inference is made. |

The only primary evidence used is the source registry at
`docs/audits/sources/wave209c-stationary/source-registry.json`: B.B. Battery
BC, HR and HRL manufacturer pages plus the Ventura 2023 manufacturer catalogue.
Every referenced snapshot is SHA-256-pinned. Retailer, distributor,
compatibility and family-only evidence was not accepted.

The exact-only manifest contains 12 records:
`bitrix:1597`, `bitrix:1606`, `bitrix:1609`, `bitrix:1612`, `bitrix:1617`,
`bitrix:1624`, `bitrix:1625`, `bitrix:1631`, `bitrix:1635`, `bitrix:1636`,
`bitrix:1640`, `bitrix:1643`.

## Guards and verification

- Full canonical registry: 17,207 rows checked.
- Live PostgreSQL collision guard: 26 source-exact candidates checked; 14
  collision groups held; no candidate had manufacturer or MPN populated after
  dry-run.
- Laravel `catalog:apply-verified-oem-identities` dry-run: exit 0, 12 records,
  zero commercial-field changes and zero publication-field changes.
- Independent dry-run initially failed because the temporary container copy did
  not include the reused Wave206 source directories. After those exact pinned
  snapshots were copied, the unchanged manifest passed.
- Import run **932** applied 12 identities. Idempotence rerun: **0 filled / 12
  unchanged**. Commercial and publication changes: **0**.
- `python -m pytest scripts/tests/test_build_rb_wave209c_stationary_evidence.py -q`:
  4 passed.

Generated evidence, the collision guard, the manifest and the dry-run receipt
are all under `docs/audits/generated/` and `docs/imports/`; they are the
machine-readable hand-off. No git commit was made.
