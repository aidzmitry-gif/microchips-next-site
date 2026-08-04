# RB LEOCH current expansion — wave 188

Date: 2026-07-29. Site: `microchips-by`.

## Result and primary sources

Twenty exact LEOCH identities absent from PostgreSQL and earlier waves were
added from manufacturer-hosted January 2026 documents:

- 15 flooded OPzS cells from
  `https://download.leoch.com/Network%20Power%20Battery/OPzV%26OPzS%20Reserve%20Power%20Solution%20LB-Tubular-PB-EN-V3.3-202601.pdf`;
- 5 LP VRLA-AGM batteries from
  `https://download.leoch.com/Network%20Power%20Battery/Leoch%20VRLA-AGM%20Series%20Product%20Brochure%20LB-VRLA-AGM-PB-EN-V4.5-202601.pdf`.

Exact voltage, C10/C20 capacity, dimensions and approximate mass were copied
per model. OPzS remains explicitly flooded/maintainable and is not represented
as AGM or maintenance-free. LP is represented as sealed VRLA AGM.

The common OPzS-style model strings are always bound to `manufacturer=LEOCH`
and their source URL. Existing `4OPzS200` was excluded before the wave because
it collided with an existing normalized identity.

## Commercial and media boundary

- availability: `on_request`;
- price and price evidence: absent;
- indexability: false;
- `Offer` schema: absent;
- image: absent because reusable rights were not established.

## Verification

- Candidate/content/preview dry-run and apply: 20/20 accepted.
- Reusable verifier: 20 products, 20 paths, zero price evidence, zero duplicate
  normalized MPN groups, passed.
- Industrial 3000 Ah filter: exactly LEOCH `24OPzS3000`.
- UPS + AGM + 4.5 Ah filter: exactly LEOCH `LP4-4.5`.
- `24OPzS3000` storefront: HTTP 200, exact capacity, `noindex`, no `Offer`.
- Final totals: 16,692 published RB rows / 16,691 canonical cards; 4,213
  published broad B2B rows / 4,212 canonical cards; 1,233 UPS-battery and
  1,043 industrial-battery rows.
- SEO audit: PASS across 16,729 routes and seven redirects, zero blockers.

All four artifacts use `leoch-wave188-2026-07-29` under `docs/imports/`.
