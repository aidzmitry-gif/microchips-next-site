# RB SEO category assignment report — 2026-07-26

## Applied result

- Target taxonomy: **19** unpublished categories, source namespace
  `full_catalog_seo_tree`.
- Input catalogue: **9,084** non-public RB product drafts.
- High-signal assignments: **5,568** (dry-run first, then one atomic apply).
- Validation errors: **0**.
- Public RB products after apply: **0**.

## Assignment policy

The source 1C group hierarchy is partly a warehouse layout and is not exposed
as customer navigation. A product is assigned only when its name/path matches
a high-signal rule (for example UPS, charger, industrial component, battery
format, device family or warehouse equipment).

The remaining **3,516** rows are deliberately unassigned. They must receive a
better classifier rule or primary-source evidence before they enter a customer
category. This prevents an artificial "Other" category and thin or misleading
SEO pages.

## Evidence files

- `docs/imports/one-c-seo-category-assignments.csv` — applied assignment input.
- `docs/audits/generated/one-c-seo-category-assignment-summary.json` — counts
  by target category.
- `docs/audits/generated/one-c-seo-category-unclassified.csv` — explicit
  follow-up queue; not a publish list.
