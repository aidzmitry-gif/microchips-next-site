# RB FIAMM FG legacy enrichment — wave 194

Date: 2026-07-29. Site: `microchips-by`.

## Scope

Wave 194 enriches only existing namespaced Bitrix materializations from the
pinned full-catalog snapshot run `763`. It neither creates a `manufacturer:*`
identity nor merges a Bitrix draft into a canonical product.

The active 15-row set is:

`bitrix:1405`, `1406`, `1407`, `1485`, `1486`, `1487`, `1546`, `2866`,
`2931`, `2939`, `2954`, `2960`, `3048`, `3179`, `3180`.

Each has a `catalog_draft_materializations` lineage row from source run `763`
and is a draft with `on_request` availability and no price. The intended
category is the existing `seo:batteries-ups` / `catalog/industrial-batteries/batteries-ups`.

## Source and evidence boundary

The source is [FIAMM FG series](https://www.fiamm.ru/equipment/FG-series/),
published by ООО «ФИАММ Индастриал РУС». The page describes its publisher as
the official FIAMM distributor for Russia and the CIS; it is not treated as a
manufacturer-primary source.

Consequently the description manifest is `dealer_backed` and `model_core`.
It may add only the source-table nominal voltage and nominal capacity at C20;
it deliberately does not establish or overwrite FIAMM/MPN fields, names,
dimensions, mass, commercial facts, images or availability.

## Explicit exclusions

The following exact canonical FIAMM records are excluded rather than receiving
a second product identity or a competing enrichment record:

| Model core | Existing canonical product | Reason |
| --- | ---: | --- |
| FG10451 | 8600 | FIAMM name already contains exact model; existing description draft 1181 |
| FG20722 | 8279 | FIAMM name already contains exact model; existing description draft 1182 |
| FG21202 | 28 | Exact FIAMM + MPN; identity candidate 16 and draft 32 already exist |
| FG21803 | 34 | Exact FIAMM + MPN; identity candidate 24 and draft 38 already exist |

`FG20451` / `bitrix:3011` is separately excluded: its full-catalog source
row is marked `hold_one_c_collision`. A namespaced draft exists only because a
prior materialization explicitly included held rows; wave194 does not bypass
that source-workflow guard.

`FG20121` and `FG20121A` remain separate model-core rows. A prefix match is
not considered an identity match.

## Commercial and publishing boundary

Both manifests contain no price or price provenance, stock, delivery,
availability change, image or Offer data. The preview command can only produce
noindex pages.

## Verification

- JSON shape check: 15 distinct external IDs and 15 distinct preview slugs.
- Description refresh passed dry-run, was staged, and 15 descriptions were
  applied. The content workflow did not change canonical manufacturer/MPN,
  price, availability or indexability.
- The source-backed `VRLA AGM` value is persisted as the canonical
  `Технология` technical attribute, so the public catalogue emits the `AGM`
  technology facet instead of silently losing a verified filter value.
- Preview dry-run and apply each accepted 15 products, two category nodes,
  zero verified prices, zero indexable URLs and zero Offers.
- Reusable verifier: 15 products, 15 distinct paths, zero price evidence,
  zero normalized-MPN duplicate groups and zero errors.
- Runtime `q=FG10121`: one exact card, HTTP 200 detail page, `noindex`,
  `on_request`, null price, no Offer, 6 V / 1.2 Ah C20 and AGM facet.
- Full `seo:audit microchips-by`: 16,858 URLs, 22 redirects and zero blockers.

## Files

- `docs/imports/rb-source-backed-description-drafts-fiamm-fg-wave194-2026-07-29.json`
- `docs/imports/rb-source-verified-preview-fiamm-fg-wave194-2026-07-29.json`
