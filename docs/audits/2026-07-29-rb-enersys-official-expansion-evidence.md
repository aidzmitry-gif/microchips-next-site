# RB EnerSys official B2B expansion evidence — wave 179

Date: 2026-07-29. Market: Belarus (`microchips-by`).

## Official scope

The wave uses only primary EnerSys product material:

- [DataSafe HX range summary](https://www.enersys.com/49160e/globalassets/documents/product-documentation/datasafe/hx/emea/datasafe_HX_range_summary_emea-en-rs-ds-hx-0223.pdf)
  for seventeen exact DataSafe HX / HX Plus model identities and common VRLA
  high-rate UPS characteristics;
- [PowerSafe V-FT range summary](https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-ft/amer/powersafe_vfrontterminal_batteryrangesummary.pdf)
  for nine exact PowerSafe V-FT model identities;
- [PowerSafe V-FT official product page](https://www.enersys.com/en-gb/products/batteries/powersafe/powersafe-v-ft/)
  for the shared 12 V, TPPL, front-terminal and telecom/industrial-UPS
  positioning.

## Identity and publication result

- Full PostgreSQL normalized-MPN/name lookup found no exact current product
  for the 26 selected models. Existing DataSafe 12HX50, DataSafe 12HX540 and
  PowerSafe 12V62F were excluded before manifest construction.
- Potentially ambiguous 12HX35 and 12V125F roots were held rather than merged.
- Candidate, description and preview dry-run/apply gates accepted 26/26.
- All 26 cards are `on_request`, have null numeric price, no Offer schema and a
  noindex canonical path under `Аккумуляторы для ИБП`.
- The full products table has zero duplicate non-null normalized MPN groups.

## Plus-model URL correction

The initial generic slug function discarded `+`, which could make an HX Plus
model collide with a future non-plus model. The generator now translates this
identity-bearing character to the literal URL token `plus`. Six current paths
were safely corrected before indexation. The preview publisher now retires an
older noindex product path with a 301 redirect whenever a verified slug changes,
and refuses to replace an indexable path through this workflow.

## Deliberately omitted

No per-model capacity, power, dimensions, terminal hardware or runtime value
was inferred from an MPN. No price, stock quantity, delivery promise or image
was copied. Manufacturer image reuse rights were not established.
