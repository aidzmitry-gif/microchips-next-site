# Wave207 — Motorola/Kenwood radio battery evidence

## Scope and no-repeat gate

- Input: `rb-b2b-next-source-batch-wave205.csv`.
- Processed exactly 104 rows: Motorola 74, Kenwood 30.
- Wave206 evidence overlap: 0 rows (all Wave206 evidence CSVs are enumerated and excluded before the scope-count assertion).
- No database mutation, publication, price, stock, description or media change was authorized.

## Evidence result

| Partition | Rows | Decision |
|---|---:|---|
| `exact_safe` | 4 | Kenwood KNB-29N, KNB-41NC, KNB-53N and KNB-56N are exact rows in the pinned first-party accessory catalogue. |
| `conflict` | 7 | Pinned Kenwood specifications contradict one or more chemistry/capacity/voltage claims in the legacy title. |
| `no_evidence` | 93 | 19 Kenwood items are absent from the pinned documents; all 74 Motorola items remain held because three official Motorola PDF routes did not yield a stable local snapshot in the bounded acquisition. |

Compatibility lists and web-index snippets were not treated as product identity. A Motorola-compatible pack is not promoted to Motorola OEM identity without a pinned primary battery source.

## Duplicate and collision gates

- Nine strict manufacturer+model groups were found among Motorola rows, including HNN9008A (3 rows), HNN9628A (4), and paired HNN4002, HNN9008, HNN9628, NNTN4851, PMNN4021, PMNN4077 and PMNN4251 rows.
- These groups remain held; no automatic collapse was attempted without exact current battery evidence.
- The four safe Kenwood MPNs were checked against current PostgreSQL `sku_normalized`/`mpn_normalized`: 4 checked, 0 live collisions.
- Laravel dry-run accepted the unchanged four-row manifest: 4 records, 0 commercial changes, 0 publication changes.

## Artifacts

- `docs/audits/sources/wave207-motorola-kenwood/snapshot-index.json`
- `docs/audits/generated/wave207-motorola-kenwood-evidence.csv`
- `docs/audits/generated/wave207-motorola-kenwood-evidence-summary.json`
- `docs/audits/generated/wave207-live-identity-collisions.json`
- `docs/audits/generated/wave207-laravel-dry-run.json`
- `docs/imports/rb-verified-oem-identities-wave207-motorola-kenwood-2026-07-29.json`

## Verification

- `python scripts/build-rb-wave207-motorola-kenwood-evidence.py` — 104 rows, final dry-run hash verified.
- `python -m pytest scripts/tests/test_wave207_motorola_kenwood_evidence.py -q --basetemp tmp/pytest-wave207-agent` — 7 passed.
- Laravel `catalog:apply-verified-oem-identities` without `--apply` — exit 0, 4 records.

The four exact identities are dry-run ready only. They were not applied to the database in this loop.
