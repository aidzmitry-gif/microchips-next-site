# RB LEOCH LPL II 2V expansion — wave 192

Date: 2026-07-29. Site: `microchips-by`.

## Result and official source

Nineteen exact LEOCH LPL II 2 V model identities absent from products, staged
data and waves 174–191 were added from the current manufacturer catalogue:

`https://download.leoch.com/Network%20Power%20Battery/Leoch%20VRLA-AGM%20Batteries.pdf`

The source labels each identity as `Model`; no separate supplier article is
invented. The `M` suffix remains identity-bearing. Exact voltage, C10 capacity,
dimensions and approximate mass are preserved per model.

## Scope and commercial boundary

- category: `catalog/industrial-batteries/batteries-industrial`;
- technology: sealed 2 V VRLA AGM stationary cell;
- source-backed applications: telecom stations, utility communications, data
  and television transmission, UPS and EPS;
- availability: `on_request`;
- price, price evidence and image: absent;
- indexability: false;
- `Offer` schema: absent.

## Verification

- Candidate dry-run/apply: 19 createable / 19 created, zero unchanged.
- Description stage/apply and preview dry-run/apply: 19/19 accepted.
- Reusable verifier: 19 products, 19 distinct paths, zero price evidence,
  zero normalized MPN duplicates and no errors.
- API query `q=LPL2`: 19 results and 19 distinct paths.
- LEOCH + AGM + 3000 Ah within the LPL2 query: exactly `LPL2-3000M`.
- LPL2-3000M storefront: HTTP 200, exact MPN and capacity, `noindex`, no
  `Offer` schema.
- Final totals: 16,792 published RB market rows / 16,791 canonical cards;
  4,313 published broad B2B rows / 4,312 canonical cards; 1,143 industrial
  battery rows.
- SEO audit: PASS across 16,829 routes and seven redirects, zero blockers.

All four wave artifacts use `leoch-lpl2-wave192-2026-07-29` under
`docs/imports/`. Waves 189–192 together form a 100-card manufacturer-backed
batch (21 + 16 + 44 + 19), with no duplicate identity or invented offer.
