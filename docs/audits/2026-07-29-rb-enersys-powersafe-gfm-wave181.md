# RB EnerSys PowerSafe GFM official expansion — wave 181

Date: 2026-07-29. Market: Belarus (`microchips-by`).

## Official evidence

Primary source: [EnerSys PowerSafe GFM range summary](https://www.enersys.com/49fbe8/globalassets/documents/product-documentation/powersafe/gfm/apac/powersafe-gfm-rs-02_0921.pdf).

The official range table establishes 12 exact module identities: 6GFM200,
6GFM250, 6GFM300, 6GFM350, 6GFM420, 6GFM500, 6GFM600, 3GFM800,
3GFM1000, 3GFM1200, 3GFM1500 and 3GFM2000. It supplies a per-model nominal
voltage, C10 capacity, module dimensions and typical module mass.

Safe common series facts applied to every card are VRLA AGM construction,
modular horizontal installation with front access, use in telecoms, power
generation, UPS and emergency lighting, no routine water addition, 15-year
design life at 20 °C and IEC 60896-21/22 compliance.

## Identity and commercial boundary

- The manufacturer candidate dry-run accepted exactly 12 new records and
  rejected no collision; the full products table still has zero duplicate
  non-null normalized MPN groups after apply.
- Every candidate passed the separate description stage/apply and preview
  dry-run/apply gates.
- All 12 cards are published only as `noindex` previews, with `on_request`,
  null price and no `Offer` schema.
- No product image was copied because the official document does not establish
  a storefront reuse licence.

## Runtime verification

Database verification found 12 published rows, 12 distinct MPNs and 12
distinct paths. Exact API queries for 6GFM200 and 3GFM2000 each return one
identity. The storefront renders the exact model-level facts. Capacity-facet
extraction was extended for explicit C10 values; the `200 А·ч` filter now
returns the 6GFM200 card, and the facet cache key carries a schema version so
old extraction results cannot survive a deployment.
