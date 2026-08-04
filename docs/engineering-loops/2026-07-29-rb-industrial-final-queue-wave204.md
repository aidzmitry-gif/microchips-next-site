# RB industrial final priority queue — Wave204

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope and no-repeat proof

Wave204 closes the last **106 untouched B2B rows** from the initial 500-row priority queue. The three partitions are disjoint and their union is exactly 106 products:

| Partition | Rows | Exact source evidence | Compatibility only | Conflict | No exact evidence |
|---|---:|---:|---:|---:|---:|
| Radio-station battery packs | 41 | 4 | 1 | 0 | 36 |
| Legacy industrial / traction cells | 34 | 1 | 0 | 8 | 25 |
| Industrial remote-control batteries | 31 | 9 | 0 | 2 | 20 |
| **Total** | **106** | **14** | **1** | **10** | **81** |

The evidence builders report zero overlap with the previously processed queue. The combined manifest builder independently confirmed `41 + 34 + 31 = 106`, with zero pairwise overlap.

## Layered identity gate

Fourteen rows had an exact model or part match in a pinned first-party source. That did not make all fourteen safe to write automatically.

The adversarial source review separated three HIAB rows (`bitrix:20059`, `20060`, `20061`) because the official source maps the replacement part to a product family but does not prove the legacy `4000/5000` generation suffix precisely enough.

The unchanged Laravel bounded-name gate held three additional identities:

- `bitrix:2239` — official Danfoss `BT06K ATEX`, while the legacy name contains only a Cyrillic lookalike and no manufacturer;
- `bitrix:20049` and `bitrix:20050` — official ELCA numeric part numbers are absent from the legacy titles.

The gate was not weakened. The final application manifest therefore contains only these eight literal-name-pinned identities:

| Product | Manufacturer | MPN |
|---|---|---|
| `bitrix:2394` | Alinco | `EBP-50N` |
| `bitrix:2395` | Alinco | `EBP-51N` |
| `bitrix:2396` | Alinco | `EBP-64` |
| `bitrix:2397` | Alinco | `EBP-65` |
| `bitrix:20045` | AUTEC | `MBM06MH` |
| `bitrix:20071` | AUTEC | `MH0707L` |
| `bitrix:20073` | AUTEC | `LBM02MH` |
| `bitrix:20075` | AUTEC | `AIRBM3V7L` |

All source snapshots were saved locally and their SHA-256 values were recomputed. The source-token checks passed for all fourteen exact-evidence rows. The Alinco and AUTEC PDF table associations were also visually inspected.

## Safe application

The manifest passed the Laravel dry-run and then filled only blank `manufacturer` and `mpn` fields:

- manifest SHA-256: `799bbc26151b5d1fb445545d2792a7c0882140dd3cdc0582c69fd23b5670dc44`;
- identities filled: **8**;
- commercial fields changed: **0**;
- publication fields changed: **0**;
- idempotence rerun: **0 filled / 8 unchanged**;
- completed import run: `924`;
- reviewed evidence audit rows: **8**.

All eight products remain drafts. Names, SKU, price, availability and publication state were not promoted.

## Commercial and duplicate guard

The deterministic read-only guard checked all 106 products in six bounded database batches:

- products / RB site products: **106 / 106**;
- current price / currency / `in_stock`: **0 / 0 / 0**;
- Offer schema / unsupported current commercial claims: **0 / 0**;
- current price evidence: **0**;
- media / verified published media: **0 / 0**;
- strict duplicate groups / candidates: **0 / 0**.

The legacy source contains 104 price claims and 106 `in_stock` claims. They were deliberately not copied because the snapshot does not prove that they are current. The output CSV was byte-identical on rerun; SHA-256: `71175ac6ff74e9fba0755b2674c093e92b7efd59a94390b657743721c8b0b644`.

No lookalike was collapsed: Alinco versus Ajetrays, AUTEC versus compatible replacement packs, and ATEX versus standard Danfoss variants remain distinct.

## Runtime and SEO verification

- all eight affected storefront URLs return HTTP **200**;
- all eight emit `noindex, nofollow`;
- post-apply SEO audit: **16,853 URLs, 97 redirects, 0 blockers**;
- combined Wave204 Python verification: **18 passed** in the final independent run;
- the combined manifest agent reported **24 passed** across its expanded Wave204 suite;
- the existing OEM application test suite had already passed **5 tests / 42 assertions**; the production image intentionally has no PHPUnit dev command.

## Main artefacts

- `docs/imports/rb-verified-oem-identities-wave204-2026-07-29.json`
- `docs/audits/generated/wave204-radio-evidence.csv`
- `docs/audits/generated/wave204-industrial-cell-evidence.csv`
- `docs/audits/generated/wave204-remote-control-evidence.csv`
- `docs/audits/generated/rb-wave204-commercial-duplicate-guard.csv`
- `docs/audits/generated/wave204-verified-oem-identities-summary.json`
- `docs/audits/sources/wave204-radio/`
- `docs/audits/sources/wave204-industrial-cells/`
- `docs/audits/sources/wave204-remote-control/`
- `scripts/build-rb-wave204-verified-oem-identities.py`
- `scripts/build-rb-wave204-commercial-duplicate-guard.py`

Wave204 completes evidence triage for the initial 500-row B2B priority queue, but it does not make the full catalogue publication-ready. The overall project stays at the last objectively verified **60%**: missing current commercial evidence, verified media and manufacturer-primary content remain separate gates.
