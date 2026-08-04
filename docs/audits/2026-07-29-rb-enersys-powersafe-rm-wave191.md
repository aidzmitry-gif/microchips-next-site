# RB EnerSys PowerSafe RM expansion — wave 191

Date: 2026-07-29. Site: `microchips-by`.

## Result and official sources

The complete 44-model PowerSafe RM range table was evaluated, rather than the
initial conservative 21-model subset. All 44 exact `EnerSys + RM <number>`
identities were absent from products, staged data and previous expansion waves,
and all passed the transactional candidate dry-run.

Official sources:

- current range page:
  `https://www.enersys.com/en/products/batteries/powersafe/powersafe-rm/`;
- model table linked from that page:
  `https://www.enersys.com/493c0d/globalassets/documents/product-documentation/powersafe/nicd/amer/us-rm-rs-003_0114.pdf`;
- 2024 utility quick-reference guide:
  `https://www.enersys.com/4aea51/globalassets/documents/marketing-literature/esg/industrial/brochures/amer/en-amer-qr-utility.pdf`.

Per-model capacity, length, width, height and unpacked mass are attributed only
to the linked January 2014 RM table. Capacity remains explicitly qualified as
C5 to 1.15 V per cell at 20 °C. It is not mixed with the 2024 guide's different
C5 endpoint.

## Adversarial holds

There is a direct unresolved first-party voltage conflict: the current RM page
reports 2 V while the 2024 EnerSys guide reports nominal 1.2 V for RM 11–1390.
Therefore the cards expose neither value. No 12/24/48 V system voltage is
inferred.

The earlier substring screen held four real RM models because unrelated product
names contained similar tokens. The exact manufacturer-plus-MPN dry-run proved
all 44 identities clean, avoiding 23 unnecessary omissions from the official
range.

## Scope and commercial boundary

- category: `catalog/industrial-batteries/batteries-industrial`;
- technology: vented Ni-Cd pocket-plate stationary cell;
- source-backed applications: mixed loads, UPS, utility and telecom;
- availability: `on_request`;
- price, price evidence and image: absent;
- indexability: false;
- `Offer` schema: absent.

## Verification

- Candidate dry-run/apply: 44 createable / 44 created, zero unchanged.
- Description stage/apply and preview dry-run/apply: 44/44 accepted.
- Reusable verifier: 44 products, 44 distinct paths, zero price evidence,
  zero normalized MPN duplicates and no errors.
- API query `q=PowerSafe RM`: 44 results and 44 distinct paths; no voltage
  facet values leaked from the conflicting sources.
- EnerSys + 400 Ah filter within the RM query: exactly `RM 400` after explicit
  C5 facet support and a facet-cache schema increment.
- RM 400 storefront: HTTP 200, exact identity and capacity, `noindex`, no
  `Offer` schema.
- Final totals: 16,773 published RB market rows / 16,772 canonical cards;
  4,294 published broad B2B rows / 4,293 canonical cards; 1,124 industrial
  battery rows.
- SEO audit: PASS across 16,810 routes and seven redirects, zero blockers.

All four wave artifacts use `enersys-rm-wave191-2026-07-29` under
`docs/imports/`.
