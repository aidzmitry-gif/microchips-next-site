# RB live category expansion — 2026-07-27

## Correction to the classification pipeline

The initial assignment source did not fully match the current RB site state.
The category builder now accepts both `external_id` and
`product_external_id` exclusion headers, supports multiple exclusion manifests,
and uses a live export of existing RB category assignments before it creates a
delta.

## Conservative technical rules

The expansion classifies only names with a technically unambiguous model or
device marker:

- CR/ER/BR/LS and similar primary-cell model codes;
- 6-FM, DTM, HRL, GPL, FIAMM FGH, CSB and BB Battery stationary model
  families;
- AC/DC and DC/DC power converters;
- battery holders, thermocardboard spacers, charge indicators and equalizers.

These rules do not infer capacity, voltage or commercial availability.

## Verification and result

- Import run 89 dry run: **119** new assignments, 0 errors, 0 publications.
- Import run 90 apply: **119** new assignments, 0 chemistry writes, 0
  publications.
- RB non-public drafts: **7,641**.
- Exactly one `full_catalog_seo_tree` leaf: **5,987**.
- No target leaf: **1,654**.
- Multiple target leaves: **0**.

The remaining queue is intentionally not forced into a catch-all category or
an indexable thin page.
