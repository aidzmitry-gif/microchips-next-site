# RB price provenance and sorting — wave 90

Date: 2026-07-28  
Site: `microchips-by`  
Scope: local catalogue only; no external publication

## Accepted commercial rule

1. An exact product price from the legacy `microchips.by` catalogue is the
   primary source.
2. If the legacy site has no price, a current 1C price may be used with the
   fixed multiplier `2.0000`.
3. A 1C fallback is rejected unless product identity, currency, observation
   time, source reference and price type are present.
4. A legacy-site price always outranks a 1C fallback, even when the 1C record
   is newer.
5. Price evidence never changes publication or availability. `Offer` schema
   remains forbidden without independently confirmed `in_stock` data.

## Implemented

- Added `site_product_price_evidences`: immutable source price, multiplier,
  calculated market price, currency, source reference, observation time,
  evidence hash and current-record marker.
- Added all-or-nothing `catalog:import-verified-prices` with dry-run as the
  default.
- Added `catalog:build-rb-price-evidence` to combine only approved
  Bitrix-to-1C identity links with the generated Bitrix price snapshot.
- Enabled price sorting only when the market has current source-backed price
  evidence. Missing prices sort last in both directions.

## Applied result

| Measure | Result |
|---|---:|
| RB site-product rows | 7,163 |
| Approved Bitrix ↔ 1C candidates | 50 |
| Exact links with a valid legacy-site price | 49 |
| Evidence rows applied | 49 |
| Site prices updated | 49 |
| Published products | 33 |
| Published products with price | 29 |
| Current `one_c_x2` rows | 0 |
| Products changed to `in_stock` | 0 |

The current 1C nomenclature snapshot contains zero prices, currencies and
price types. Therefore the `×2` fallback is implemented and tested but was not
used. Direct read-only OData access from the Codex execution environment was
blocked by Windows (`WinError 10013`); no currency or price type was guessed.

## Adversarial checks

- Live `microchips.by` page for legacy element `1401` shows Delta DT 12012 at
  `20 руб.`; the local API returns the exact linked canonical product at
  `20.00 BYN`.
- The approved identity queue produced 47 prices. Two additional published
  FIAMM products (`12FGH23`, `12FGH36`) were exact brand+MPN matches in both
  the Bitrix snapshot and the live legacy catalogue, bringing the total to 49.
- Dry-runs validated 47 + 2 rows and wrote nothing.
- Apply created 49 evidence rows and updated 49 site prices.
- Re-running the same evidence is idempotent through a SHA-256 evidence key.
- Wrong site currency aborts the entire input file.
- A newer `one_c_x2` record cannot overwrite a legacy-site price.
- All 49 priced products remain `availability=on_request`; no stock claim or
  `Offer` schema was introduced.

## Verification

- Laravel targeted suite: 15 tests, 100 assertions — PASS.
- Price importer suite: 4 tests, 20 assertions — PASS.
- Frontend targeted suite: 23 tests — PASS.
- TypeScript `tsc --noEmit` — PASS.
- Next.js 16.2.10 production build — PASS.
- Runtime API: ascending first price `7.00`, descending first price `1388.00`,
  six missing prices placed last — PASS.
- SSR `/catalog`: both price sorting options and `20.00 BYN` present — PASS.
- `verify-rb-prototype.ps1`: all four RB prototypes — PASS.
- `seo:audit microchips-by`: 42 URLs, zero blocking issues — PASS.
- `site:launch-preflight`: intentionally NOT passed; the site still has no
  indexable URL and still requires external DNS/TLS, analytics/Webmaster,
  redirect cutover and post-launch evidence.

## Readiness interpretation

This wave closes the price-provenance mechanism and prices 87.9% of the
currently published preview (`29 / 33`). It does **not** make the full
7,163-product RB catalogue commercially complete: strict price coverage of the
full RB site scope is `49 / 7,163 = 0.68%` until further exact legacy mappings
or a verified 1C price snapshot are available.
