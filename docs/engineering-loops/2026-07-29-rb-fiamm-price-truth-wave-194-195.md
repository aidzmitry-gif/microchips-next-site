# RB FIAMM and commercial-truth loop — waves 194–195

Date: 2026-07-29. Site: `microchips-by`.

## Result

- Enriched and exposed 15 existing FIAMM FG Bitrix identities without creating
  a second product identity. Four existing canonical products and one held
  Bitrix/1C collision were deliberately excluded.
- Added source-backed voltage, C20 capacity and VRLA AGM technology. The
  technology now participates in the public catalogue facet; dealer evidence
  still does not promote manufacturer or MPN into canonical identity fields.
- Rebuilt the reproducible RB price manifest from current exact identity links:
  55 `legacy_site` rows and zero `one_c_x2` rows. Dry-run validation passed and
  made no database changes.
- Confirmed the database still has 57 current price-evidence rows, 34 published
  numeric-price cards and zero `in_stock` claims. Two current price records are
  separately reviewed exact FIAMM links and are not reproduced by the generic
  approved-link builder.

## Commercial-data safety change

An Offer is no longer emitted merely because a product happens to have a price
and `in_stock` flag. Runtime resolution now additionally requires current price
evidence matching the visible price and site currency. The Offer node itself
must contain the same price/currency and `InStock`; otherwise it is stripped.
The release auditor blocks missing evidence and mismatched Offer values.

The price importer continues to implement the accepted rule:

1. exact legacy public price wins;
2. otherwise an exact approved 1C identity may use `source price × 2`;
3. 1C fallback requires a positive price, BYN currency, price type and observed
   timestamp;
4. price never changes availability.

The current 1C inventory has zero positive prices, zero currency values and zero
price types, so applying `×2` now would fabricate data. The mechanism remains
ready for the next complete price export but produced zero rows in this wave.

The price-manifest builder now streams the 24k+ site-product scope and selects
only required 1C commercial columns. The previous full Eloquent hydration of
large source payloads exhausted the default PHP memory limit; the same full
build now succeeds without a raised limit.

## Verification

- PHPUnit catalogue/commercial targeted suite: 45 tests, 227 assertions — PASS.
- FIAMM verifier: 15 products, 15 paths, zero price evidence, zero duplicate
  normalized MPN groups — PASS.
- Runtime FIAMM sample: HTTP 200, `noindex`, AGM/6 V/C20 facets, null price and
  no Offer — PASS.
- `seo:audit microchips-by`: 16,858 URLs, 22 redirects, zero blockers — PASS.
- Docker: PostgreSQL, Redis, backend, worker, nginx and frontend healthy.
- Full 55-row price build and importer dry-run at the default PHP memory limit
  — PASS.

## Evidence files

- `docs/imports/rb-source-backed-description-drafts-fiamm-fg-wave194-2026-07-29.json`
- `docs/imports/rb-source-verified-preview-fiamm-fg-wave194-2026-07-29.json`
- `docs/imports/rb-price-evidence-wave-195-2026-07-29.csv`
- `docs/audits/2026-07-29-rb-fiamm-fg-wave194.md`
