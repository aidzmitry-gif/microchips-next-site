# RB EnerSys PowerSafe OPzV official expansion — wave 182

Date: 2026-07-29. Market: Belarus (`microchips-by`).

## Official evidence

Primary source: [EnerSys PowerSafe OPzV range summary](https://www.enersys.com/4acdcc/globalassets/documents/product-documentation/powersafe/opzv/amer/en-rs-amer-ps-opzv-0923.pdf).

The official range table establishes 14 exact 2 V cell identities from
`4 OPzV 200` through `24 OPzV 3000`, with per-model C10 capacity, dimensions
and typical mass. The series uses tubular VRLA GEL technology and is specified
for telecommunications, power generation and distribution, signalling,
computing systems, emergency lighting and automation. The source also states
a 20-year design life at 20 °C, vertical or horizontal installation, no water
addition, and IEC 60896-21/22 and DIN 40742 compliance.

## Import and duplicate boundary

- The dry-run accepted exactly 14 new records before persistence; all 14 then
  passed the separate description and preview gates.
- Database verification found 14 published cards, 14 distinct MPNs and 14
  distinct product paths. The full products table retains zero duplicate
  non-null normalized MPN groups.
- Every card remains `noindex`, `on_request`, with null price and no `Offer`.
- No source image was copied because no suitable storefront reuse licence was
  established.

## Runtime verification

The exact `4 OPzV 200` API result exposes GEL, 2 В and 215 А·ч. Combining all
three filters returns exactly that product. Its storefront route returns HTTP
200, displays the exact model and C10 capacity, contains `noindex`, and emits
no commercial `Offer` schema.
