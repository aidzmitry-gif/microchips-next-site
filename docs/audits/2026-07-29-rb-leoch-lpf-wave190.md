# RB LEOCH LPF expansion — wave 190

Date: 2026-07-29. Site: `microchips-by`.

## Result and primary source

Sixteen exact LEOCH LPF front-terminal VRLA-AGM model identities absent from
PostgreSQL and waves 174–189 were added from the manufacturer-hosted catalogue:

`https://download.leoch.com/Network%20Power%20Battery/Leoch%20VRLA-AGM%20Batteries.pdf`

The source's exact model strings are used as MPNs. Parenthesized variants such
as `LPF12-100(P)` and `LPF12-190(P)`, plus the `A` and `V` suffix variants,
remain independent identities and receive distinct URLs. Exact 12 V voltage,
C10 capacity, dimensions and source-labelled gross mass are preserved per
model.

## Scope and commercial boundary

- category: `catalog/industrial-batteries/batteries-industrial`;
- technology: sealed front-terminal VRLA AGM;
- source-backed applications: telecom/network equipment, UPS, power-station
  systems and local networks;
- availability: `on_request`;
- price and price evidence: absent;
- indexability: false;
- `Offer` schema: absent;
- image: absent because an exact reusable asset and rights basis were not
  established.

## Verification

- Candidate dry-run/apply: 16 createable / 16 created, zero unchanged.
- Description stage/apply and preview dry-run/apply: 16/16 accepted.
- Reusable verifier: 16 products, 16 distinct paths, zero price evidence,
  zero duplicate normalized MPN groups and no errors.
- API query `q=LPF12`: exactly 16 results and 16 distinct paths.
- LEOCH + AGM + 200 Ah filter within the LPF query: exactly `LPF12-200`.
- LPF12-200 storefront: HTTP 200, exact MPN and capacity, `noindex`, no
  `Offer` schema.
- Final totals: 16,729 published RB market rows / 16,728 canonical cards;
  4,250 published broad B2B rows / 4,249 canonical cards; 1,080 industrial
  battery rows.
- SEO audit: PASS across 16,766 routes and seven redirects, zero blockers.

All four wave artifacts use `leoch-lpf-wave190-2026-07-29` under
`docs/imports/`.
