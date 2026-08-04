# RB mobile/POS/data-capture catalogue — Wave203

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope and no-repeat proof

Wave203 was built from the 251 untouched rows remaining after the Wave201/202 industrial queue. Two Wave174 IDs were removed before research. The selected batch contains **143 new B2B battery cards** and has zero overlap with the earlier processed sets.

The batch was split into three non-overlapping research partitions:

| Partition | Rows | Exact snapshot-backed | Compatibility only | Conflict | No exact evidence |
|---|---:|---:|---:|---:|---:|
| Payment / POS terminals | 42 | 1 | 18 | 1 | 22 |
| Major data-capture brands | 74 | 0 | 3 | 13 | 58 |
| Remaining mobile/POS brands | 27 | 3 | 6 | 1 | 17 |
| **Total** | **143** | **4** | **27** | **15** | **97** |

The partition union is exactly 143 IDs; pairwise overlap and uncovered rows are both zero.

## Legacy claims rejected

Official sources exposed concrete errors in legacy titles. Examples:

- Ingenico `F12432566`: official **2900 mAh**, legacy **3000 mAh**;
- Handheld `NX8-1004`: official **5200 mAh**, legacy **6800 mAh**;
- M3 Mobile `SM20`: official **4100 mAh**, legacy **4200 mAh**;
- M3 SMART: official **2200 mAh**, legacy **2000 mAh**;
- Opticon H-27: official **2860 mAh**, legacy **3000 mAh**;
- Opticon PX-35: official battery part `BTR0400`, legacy title names `1400-203047G`;
- Leica Zeno 5: official **3600 mAh**, legacy **2400 mAh**.

No disputed value was promoted to canonical identity, specification, price or schema.

## Reproducible exact evidence

Only four rows passed the exact identity gate. For each, the current first-party HTML/PDF was saved locally, hashed and checked for exact model/part tokens:

| Product | Applied identity | Snapshot SHA-256 |
|---|---|---|
| `bitrix:12398` | Verifone / `BPK268-001-01-A` | `de1a95294ce8c1c7bb89218f00de39b124a9b1db2f65d665dd3c0f1b196d0961` |
| `bitrix:12204` | Cino / `BT2100` | `a94c49b26ad693e2a933a44be41de579aba2045113592f8d1e7ee829c6f3325b` |
| `bitrix:12304` | KOAMTAC / `KDC-BAT100` | `06edd33f7f1e30baf849e6c78a42cf7bf8e0e9a5aa698541df824d0491bb83b1` |
| `bitrix:12329` | NCR Orderman / `5555-0105-8801` | `6aa86d554c0171e1c624f88e9c034192c0e9839d40879703010d0686d497c95c` |

KOAMTAC page 2 and Orderman page 40 were additionally rendered and visually inspected. A missing, changed or token-incomplete snapshot automatically moves a row to hold and clears its replacement manufacturer/MPN.

## Safe application

The combined manifest passed the Laravel dry-run and then filled only the four previously blank `manufacturer` and `mpn` pairs.

- manifest SHA-256: `8f2a6430588d2e6f9357856a73cd0f4e98dbe1ca5d43cfbd9c7c773744af7371`;
- identities filled: **4**;
- commercial fields changed: **0**;
- publication fields changed: **0**;
- idempotence rerun: **0 filled / 4 unchanged**;
- one completed import run and four `reviewed_evidence` audit rows;
- product names, SKU and draft status remained unchanged.

The four pages remain HTTP 200 with `noindex, nofollow`. Unsupported legacy capacity/compatibility text is therefore not promoted to indexable SEO content.

## Commercial and duplicate guard

The read-only guard processed all 143 products in eight bounded Laravel/PostgreSQL batches:

- products / RB site products: **143 / 143**;
- current price / currency / `in_stock`: **0 / 0 / 0**;
- Offer schema / unsupported current commercial claims: **0 / 0**;
- price evidence: **0**;
- media / verified published media: **0 / 0**;
- legacy drafts / manufacturer-primary drafts: **143 / 0**.

The old Bitrix data contained a price for all 143 rows and `IN_STOCK=Y` for 125. Those stale commercial claims were not copied.

The guard found 11 strict model/part + voltage + capacity candidate groups (24 cards). All remain `safe_to_apply=false`: the same tokens do not prove the same housing, connector or physical battery variant. No automatic duplicate collapse was performed in Wave203.

## Verification

- Wave203 preparation/evidence/manifest suite: **22 passed** in the independent final run;
- full suite reported by the combined guard: **23 passed**;
- OEM apply command: **5 tests, 42 assertions passed**;
- commercial guard deterministic CSV SHA-256: `6316ace975a8a871a899c4df8b0402ca124911b2efa4de76dc903c98fcd2edf6`;
- Laravel production backend build: **passed**;
- runtime: four pages **200**, all `noindex, nofollow`;
- post-apply SEO audit: **16,853 URLs, 97 redirects, 0 blockers**.

## Main artefacts

- `docs/imports/rb-verified-oem-identities-wave203-2026-07-29.json`
- `docs/audits/generated/wave203-pos-evidence.csv`
- `docs/audits/generated/wave203-capture-evidence.csv`
- `docs/audits/generated/wave203-remaining-evidence.csv`
- `docs/audits/generated/rb-wave203-commercial-duplicate-guard.csv`
- `docs/audits/sources/verifone-wave203/`
- `docs/audits/sources/wave203-remaining/`
- `scripts/build-rb-wave203-verified-oem-identities.py`
- `scripts/build-rb-wave203-commercial-duplicate-guard.ps1`

The overall project remains at the last objectively confirmed **60%** threshold. Wave203 materially improves catalogue correctness and evidence provenance, but does not by itself complete the weighted requirements needed for 70% overall readiness.
