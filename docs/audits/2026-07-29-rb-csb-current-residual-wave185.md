# RB current CSB residual expansion — wave 185

Date: 2026-07-29. Site: `microchips-by`.

## Result

The current CSB range was checked after excluding every series already covered
by waves 174–184 and every exact identity already in PostgreSQL. Only nine
safe net-new MPNs remained; the wave did not manufacture extra SKUs from power
variants that have no independent manufacturer part number.

- Calor XHT-FT: `XHT7000FT`, `XHT7700FT`, `XHT8000FT`, `XHT9000FT`;
- XTV-WT: `XTV1272F2FR-WT`, `XTV12120F2FR-WT`, `XTV12200FR-WT`;
- RE 48V: `48RE1200`;
- PowerBox: `PB-300`.

Primary sources are the 2026 CSB catalogue and the individual June 2026
XHT7000FT/XHT7700FT data sheets recorded in the source manifest.

## Adversarial holds

- Catalogue dimensions for XHT8000FT and XHT9000FT were not copied because
  their height presentation differs from the two current individual sheets.
- The unusual catalogue dimension row for 48RE1200 was not copied; exact MPN,
  voltage, capacity and typical mass remain source-backed.
- PB-300 is classified as a power/energy-storage system, not a monobloc UPS
  battery. A Cameron Sino name substring is not an MPN match and was rejected
  as a false duplicate.
- No price, stock claim or image was inferred.

## Verification

- Candidate dry-run/apply: 9 createable/created, zero collisions.
- Description and preview dry-run/apply: 9/9 accepted.
- Reusable verifier: 9 products, 9 paths, zero price evidence, zero duplicate
  normalized MPN groups, passed.
- API `q=XHT`: four exact models; CSB + AGM + 20 Ah industrial filter:
  `XTV12200FR-WT` only; API `q=PB-300`: one result with null price.
- PB-300 storefront: HTTP 200, 72 kWh visible, `noindex`, no `Offer`.
- Post-wave SEO audit: PASS across 16,661 routes, zero blockers.

Artifacts use the `csb-wave185-2026-07-29` naming convention under
`docs/imports/`, with the reviewed source in
`rb-manufacturer-series-csb-wave185-source.json`.
