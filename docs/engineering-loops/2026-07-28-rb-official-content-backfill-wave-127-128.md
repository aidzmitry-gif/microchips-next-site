# RB official content backfill — Waves 127–128

## Result

- Wave 127 processed 57 new Robiton, Panasonic and PKCELL clusters. It applied
  21 descriptions and moved all unsupported assembled packs, terminal variants
  and missing exact models into the hold ledger.
- Wave 128 processed 27 new Ventura, Delta and Sonnenschein clusters. It
  applied 17 Ventura descriptions; Delta and Sonnenschein remained fail-closed
  because only distributor-hosted exact documents were found.
- Applied RB description coverage increased from 450 to 488 records. No price,
  availability, warranty, image, publication or indexation state changed.
- The no-repeat hold-product set increased to 2,959 records. The evidence
  ledger contains 264 unique hold clusters.

## Contract corrections caught before write

- Robiton model cores containing marketing words before the actual code
  (`DECT`, `SIBERIA`, `SOLAR`) failed literal boundary validation. They were
  narrowed to the exact code present in the imported product name.
- Panasonic `VL-3032/F2N` used the unsupported `exact_model` scope. It was
  corrected to `exact` with an explicit MPN before staging.

All corrected manifests then passed both staging and content dry-runs.

## Current counters

| Metric | Value |
|---|---:|
| RB site products | 7,015 |
| Applied `ru-BY` descriptions | 488 / 7,286 (6.70%) |
| Current source-backed prices | 57 |
| Verified published media products | 44 |
| Strictly complete cards | 44 / 7,286 (0.60%) |
| Cumulative reviewed hold products | 2,959 |
| Unique hold clusters | 264 |

Description throughput is no longer the limiting factor for strict card
completion. Exact rights-safe product images are the active bottleneck; a card
without such an image is deliberately not counted as complete.

## Queue rollover

Wave 129 contains 31 new research clusters after the cumulative exclusions:
Delta 13, B.B. Battery 6, CSB 5, Panasonic 2, FIAMM 2, Sonnenschein 1, BAE 1
and Kijo 1. The queue excludes all 2,959 previously reviewed hold products.

## Verification

- Wave 127 applied 19 + 2 descriptions through staging dry-run, staging apply,
  content dry-run and content apply.
- Wave 128 applied 10 + 7 descriptions through the same four gates.
- No commercial or publication fields changed.
- Local `/catalog` and `/contacts` returned HTTP 200; catalogue SSR contained
  the catalogue title.
- Docker services remained healthy.

## Main artifacts

- `docs/imports/rb-research-holds-wave-128.csv`
- `docs/audits/generated/rb-known-hold-products-wave-128-cumulative.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-128-next.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-129-summary.json`

No commit or push was performed.
