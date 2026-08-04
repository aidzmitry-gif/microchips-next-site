# RB full-catalog denominator correction — wave 147

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`

## Outcome

The 1,569-row Bitrix snapshot used by waves 138–146 is the bounded batteries
and UPS focus, not the complete `microchips.by` catalogue. It must not be used
as the denominator for full-catalogue readiness.

The authoritative complete-source inventory is:

| Source measure | Count |
|---|---:|
| Bitrix rows | 17,207 |
| Active Bitrix rows | 17,189 |
| Inactive Bitrix rows | 18 |
| 1C product rows | 9,123 |
| 1C group rows | 86 |
| Active Bitrix rows with a supplied 1C link | 867 |
| Active Bitrix rows without a proven 1C link | 16,322 |

The current RB database state, verified directly in PostgreSQL after all later
scope and duplicate clean-up waves, is:

| Current RB state | Count |
|---|---:|
| `site_products` | 7,011 |
| Published products | 242 |
| Unpublished drafts | 6,769 |
| Products with a current price value | 57 |
| Products assigned to a category | 7,011 |
| Draft electronic-component assignments | 1,141 |
| Published electronic-component products | 0 |

The earlier 1C staging wave created 9,084 drafts after excluding 39 obvious
service/non-product rows. The smaller current value of 7,011 is the result of
subsequent explicit scope and duplicate clean-up and is therefore the current
database evidence; the historical 9,084 count must not be reported as the
current storefront state.

## Full Bitrix identity state

The one-row-per-Bitrix-ID canonical registry contains 17,207 rows and does not
perform fuzzy merges:

| Identity status | Count |
|---|---:|
| unresolved identity | 16,275 |
| one-C collision candidate | 575 |
| linked candidate | 140 |
| linked exact name | 145 |
| duplicate candidate | 54 |
| inactive source | 18 |

A duplicate candidate remains evidence for review, not authorization to merge
or delete a product.

## Taxonomy evidence

- 17,189 active Bitrix rows already have one proposed target leaf in the
  full-catalogue taxonomy evidence.
- The proposal has 17 target leaves under nine roots (19 category rows when
  navigation parents are included).
- The old catalogue contains 489 product-bearing paths: 168 launch candidates,
  81 content-required paths, 211 merge-or-noindex paths and 29 navigation-only
  paths.
- Electronic components remain excluded from publication. Existing electronic
  assignments are drafts only and have zero published products.

## Readiness accounting correction

Full-catalogue coverage must use 17,189 active Bitrix rows as its source
denominator. The 1,569-row batteries/UPS focus may still have a separate slice
metric, but it cannot be presented as the full `microchips.by` catalogue.

Current visible coverage is therefore `242 / 17,189 = 1.41%`. This is a
storefront visibility metric, not a quality-complete or SEO-indexable metric.

## Verification

- Source summaries:
  - `docs/audits/generated/full-catalog-inventory-summary.json`;
  - `docs/audits/generated/full-catalog-canonical-registry-summary.json`;
  - `docs/audits/generated/full-catalog-seo-tree-summary.json`;
  - `docs/audits/generated/full-catalog-taxonomy-summary.json`.
- PostgreSQL read-only audit:
  - 7,011 RB site products;
  - 242 published;
  - 6,769 drafts;
  - 57 priced;
  - 1,141 electronic-component assignments and zero published in that branch.
- Docker services were healthy during the audit.

