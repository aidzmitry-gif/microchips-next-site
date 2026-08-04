# RB Wave208-S — Casil, ROBITON and Minamoto exact identity gate

Date: 2026-07-29  
Scope: exactly 19 rows from `rb-b2b-next-source-batch-wave205.csv` — Casil 11, Robiton 7, Minamoto 1.  
Database application: **Import run 931 completed**.

## Outcome

| Partition | Rows | Meaning |
|---|---:|---|
| `exact_safe` | 15 | Exact official product identity, no strict full-name duplicate, no live MPN/SKU collision, passed the Laravel dry-run manifest gate. |
| `conflict` | 1 | Exact official identity exists, but the current bounded-name matcher cannot validate the standalone zero token in `VRLA12-0.8`; excluded fail-closed. |
| `no_evidence` | 3 | No current exact first-party model evidence; no identity inference and no manifest row. |

The official-source pass established 16 exact model identities: 10 Casil and 6 ROBITON. The final manifest contains 15 rows: 10 Casil and 5 ROBITON.

## Source policy

- Casil evidence is pinned from exact product-detail pages at `en.casilbattery.com`, published by Chee Yuen Plastic Products (Huizhou) Co., Ltd., the official brand owner.
- ROBITON evidence is pinned from exact product pages at `www.robiton.ru`.
- Retailer snippets, compatibility-only claims, search-result text and dealer mirrors were rejected.
- Casil legacy detail pages prove brand and exact model only. Chemistry, voltage and capacity are deliberately not imported from those pages.
- Every accepted source has a local HTML snapshot, SHA-256, required exact tokens and token counts in `snapshot-index.json`.

## Fail-closed rows

| External ID | Legacy model | Partition | Reason |
|---|---|---|---|
| `bitrix:1191` | ROBITON VRLA4-3 | `no_evidence` | No exact current official ROBITON product page/catalogue entry found. |
| `bitrix:1409` | Casil CA1213 | `no_evidence` | The current official catalogue exposes CA1212, which is not accepted as proof of CA1213. |
| `bitrix:1543` | Minamoto MB12180 | `no_evidence` | The current official Minamoto domain provides no exact MB12180 product evidence. |
| `bitrix:1399` | ROBITON VRLA12-0.8 | `conflict` | Official exact page is pinned, but Laravel `ModelCoreIdentityMatcher` drops the standalone `0` token and rejects the name/MPN pair. The row stays outside the manifest until matcher coverage is corrected and retested. |

## Duplicate and live collision guards

- Canonical registry scanned: 17,207 rows.
- Strict normalized full-name duplicate groups for the 19-row scope: 0.
- Current Docker PostgreSQL checked for all 16 exact candidates using normalized MPN against both `products.mpn_normalized` and `products.sku_normalized` on other products.
- Live collision rows: 0.
- The live guard is stored separately so the evidence builder fails if the checked candidate count or query result is incomplete.

## Laravel dry-run

Command executed without `--apply`:

```text
php artisan catalog:apply-verified-oem-identities microchips-by /tmp/wave208s/docs/imports/rb-verified-oem-identities-wave208s-stationary-2026-07-29.json
```

Final result: exit code 0, mode `dry_run`, 15 records, manifest SHA-256 `4bfe78d3250554af08a6c604c5792d56f956888dbe5472d4f588d43849e23149`.

After the independent dry-run, import run 931 applied the unchanged manifest:

- identities filled: **15**;
- already identical: **0**;
- commercial fields changed: **0**;
- publication fields changed: **0**.

The idempotence rerun returned `0 filled / 15 unchanged`.

## Verification

```text
python scripts/acquire-rb-wave208s-stationary-official-evidence.py
  sources: 16; all pinned hashes and required tokens valid

python scripts/build-rb-wave208s-stationary-evidence.py
  rows: 19; exact_safe: 15; conflict: 1; no_evidence: 3; manifest: 15

python -m pytest scripts/tests/test_build_rb_wave208s_stationary_evidence.py -q -p no:cacheprovider
  6 passed
```

## Artifacts

- `scripts/acquire-rb-wave208s-stationary-official-evidence.py`
- `scripts/build-rb-wave208s-stationary-evidence.py`
- `scripts/tests/test_build_rb_wave208s_stationary_evidence.py`
- `docs/audits/sources/wave208s-stationary/`
- `docs/audits/generated/rb-wave208s-stationary-evidence.csv`
- `docs/audits/generated/rb-wave208s-stationary-evidence.summary.json`
- `docs/audits/generated/wave208s-stationary-live-identity-collisions.json`
- `docs/audits/generated/wave208s-stationary-laravel-dry-run.json`
- `docs/imports/rb-verified-oem-identities-wave208s-stationary-2026-07-29.json`

The manifest is evidence-safe, independently dry-run-verified, applied and idempotent.
