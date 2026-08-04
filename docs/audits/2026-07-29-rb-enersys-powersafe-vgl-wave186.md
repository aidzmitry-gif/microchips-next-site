# RB EnerSys PowerSafe VGL expansion — wave 186

Date: 2026-07-29. Site: `microchips-by`.

## Result and evidence

Twenty-five absent exact PowerSafe VGL identities were created and published
as noindex industrial-battery previews. Primary model-level source:

`https://www.enersys.com/49a681/globalassets/documents/product-documentation/powersafe/vgl/amer/en-rs-amer-ps-vgl-0524.pdf`

The 2024 EnerSys table supplies exact five-hour capacity to 1.00 V/cell at
20 °C, dimensions and typical mass. The shared description uses only facts
from the same document: valve-regulated Ni-Cd pocket-plate construction, top
terminals, 1–100 hour discharge coverage, recombination and temperature range.

## Source-conflict boundary

A current EnerSys web field says 2 V while the official utility reference
guide describes the VGL cell as 1.2 V. Nominal voltage was therefore omitted
from all 25 cards. Chemistry was not used to infer it, and the conflicting web
value was not allowed into the voltage facet.

## Verification

- Candidate dry-run/apply: 25 createable/created, zero collisions.
- Description and noindex-preview dry-run/apply: 25/25 accepted.
- Reusable verifier: 25 products and paths, zero price evidence, zero duplicate
  normalized MPN groups, zero errors, passed.
- API `q=VGL`: 25 cards, 25 paths and zero numeric prices.
- EnerSys + documented Ni-Cd technology + 420 Ah filter: exactly VGL 420.
- VGL 420 storefront: HTTP 200, exact capacity, `noindex`, no `Offer`.
- Current catalogue: 16,649 published RB rows / 16,648 canonical cards;
  4,170 broad B2B rows / 4,169 canonical cards; 1,005 industrial cards.
- SEO audit: PASS across 16,686 routes and seven redirects, zero blockers.

All four wave artifacts use the `enersys-wave186-2026-07-29` naming convention
under `docs/imports/`. Availability remains `on_request`; price, image and
commercial market claims remain absent.
