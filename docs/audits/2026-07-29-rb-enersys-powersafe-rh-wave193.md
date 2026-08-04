# RB EnerSys PowerSafe RH expansion — wave 193

Date: 2026-07-29. Site: `microchips-by`.

## Result and official sources

The complete 29-model PowerSafe RH table, not the initial conservative
16-model subset, was evaluated and imported. Exact manufacturer-plus-MPN
checks found no existing or staged EnerSys RH identity.

Official sources:

- current range page:
  `https://www.enersys.com/en/products/batteries/powersafe/powersafe-rh/`;
- exact model table linked from that page:
  `https://www.enersys.com/493c0d/globalassets/documents/product-documentation/powersafe/nicd/amer/us-rh-rs-003_0114.pdf`;
- 2024 utility quick-reference guide:
  `https://www.enersys.com/4aea51/globalassets/documents/marketing-literature/esg/industrial/brochures/amer/en-amer-qr-utility.pdf`.

Per-model capacity, dimensions and unpacked mass are attributed only to the
linked January 2014 RH table. Capacity remains qualified as C5 to 1.00 V per
cell at 20 °C. The current product page confirms the 10–800 Ah range,
high-current short-duration purpose and continued availability of the table.

## Adversarial holds

The current RH page reports 2 V while the 2024 official EnerSys guide reports
nominal 1.2 V for RH. The range table does not resolve that discrepancy, so no
nominal-voltage facet is published. Broad substring matches such as `H100` and
`CS-SRH200SL` were rejected as unrelated identities rather than false duplicates.

## Scope and commercial boundary

- category: `catalog/industrial-batteries/batteries-industrial`;
- technology: vented Ni-Cd pocket-plate stationary cell;
- source-backed applications: engine starting, UPS and utility systems;
- availability: `on_request`;
- price, price evidence and image: absent;
- indexability: false;
- `Offer` schema: absent.

## Verification

- Candidate dry-run/apply: 29 createable / 29 created, zero unchanged.
- Description stage/apply and preview dry-run/apply: 29/29 accepted.
- Reusable verifier: 29 products, 29 distinct paths, zero price evidence,
  zero normalized MPN duplicates and no errors.
- API query `q=PowerSafe RH`: 29 results, 29 distinct paths and no voltage
  facet values.
- EnerSys + 800 Ah filter within the RH query: exactly `RH 800`.
- RH 800 storefront: HTTP 200, exact identity and capacity, `noindex`, no
  `Offer` schema.
- Final totals: 16,821 published RB market rows / 16,820 canonical cards;
  4,342 published broad B2B rows / 4,341 canonical cards; 1,172 industrial
  battery rows.
- SEO audit: PASS across 16,858 routes and seven redirects, zero blockers.

All four wave artifacts use `enersys-rh-wave193-2026-07-29` under
`docs/imports/`.
