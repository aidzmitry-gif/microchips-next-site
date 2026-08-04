# RB CSB XTV official B2B expansion evidence — wave 175

Date: 2026-07-29. Market: Belarus (`microchips-by`).

## Source and scope

Primary source: [CSB XTV Series](https://csb-battery.com/product/xtv-series/).

The manufacturer page explicitly lists eight individual models: XTV1272,
XTV1285, XTV12120, XTV12200, XTV12550, XTV12800, XTV121000 and XTV121100.
It describes XTV as a 12 V VRLA-AGM series for float standby applications in
extreme-temperature environments, with an operating range of −20 to +50 °C
and design life up to 12 years in standby service.

## Identity and duplicate decision

- A full PostgreSQL lookup across normalized `mpn`, `sku`, product names and
  existing CSB records found no current XTV product identity.
- All eight new records use deterministic external IDs
  `manufacturer:csb:<MPN>` and exact manufacturer MPNs.
- The import command rejects an existing normalized SKU/MPN before creating a
  candidate. Re-running the same manifest is idempotent.

## Deliberately omitted claims

- Per-model capacity, dimensions, mass and terminal type are not inferred from
  model names. They require the individual datasheet in a later enrichment
  pass.
- No manufacturer image was copied because the official page does not grant a
  reuse right suitable for local storefront storage.
- No price, stock quantity, delivery date, warranty term or `Offer` was
  created.

## Follow-up official series

The same controlled expansion was then applied to the manufacturer-listed
[CSB XHRL](https://csb-battery.com/product/xhrl-series/) and
[CSB XHRL-FT](https://csb-battery.com/product/xhrl-ft-series/) model sets:
ten XHRL and four XHRL-FT identities. The source pages establish the listed
models, high-rate standby/UPS purpose, EMEA positioning and up-to-10-year
standby design life. XHRL-FT additionally establishes a 12 V front-terminal
series. Model-specific capacities and dimensions remain omitted until each
individual datasheet is processed.

## Cyclic and stationary expansion — wave 177

The next bounded expansion used three additional official CSB series pages:

- [CSB EVX](https://csb-battery.com/product/evx-series/) — eleven listed 12 V
  VRLA-AGM models for cyclic and electric-mobility applications;
- [CSB EVH](https://csb-battery.com/product/evh-series/) — four listed 12 V
  VRLA-AGM models for enhanced cyclic service;
- [CSB MSJ](https://csb-battery.com/product/msj-series/) — nine listed 2 V
  VRLA-AGM models for stationary standby and telecommunications.

The importer created exactly 24 new identities. Full-catalog checks found no
pre-existing exact normalized MPN for these models and no repeated normalized
MPN or normalized product name after import. EVX and EVH were assigned to
`Тяговые аккумуляторы`; MSJ was assigned to `Промышленные аккумуляторы`.

Only facts established at series level were applied. Per-model capacity,
dimensions, weight, terminal type and discharge tables were deliberately not
inferred from the model number. All cards remain noindex, `on_request`, without
a numeric price or Offer schema. No manufacturer image was copied because an
explicit storefront-reuse grant was not established.

## High-rate UPS expansion — wave 178

Five further current official CSB series pages established 22 absent exact
model identities:

- [XPL](https://csb-battery.com/product/xpl-series/) — eight top-terminal
  high-rate backup models;
- [XPL-FT](https://csb-battery.com/product/xpl-ft-series/) — four 12 V
  front-terminal data-centre models;
- [HR](https://csb-battery.com/product/hr-series/) — two small-output UPS
  backup models not already in the catalogue;
- [HRL](https://csb-battery.com/product/hrl-series/) — four long-life,
  high-rate backup models not already in the catalogue;
- [UPS](https://csb-battery.com/product/ups-series/) — four high-power-discharge
  models for UPS and data-centre applications.

All 22 candidates passed the normalized identifier collision gate before
creation. The known cross-brand `HR1290W` collision was deliberately omitted,
as were models already represented in the current catalogue. The same strict
boundary remains in force: no model-specific capacity or power is inferred
from an MPN, no numerical price or stock claim is created, and no source image
is copied without a suitable reuse grant.

## Industrial stationary expansion — wave 180

Five further current official CSB series pages established 24 absent exact
model identities:

- [GPL](https://csb-battery.com/product/gpl-series/) — three remaining
  long-life standby models;
- [TPL](https://csb-battery.com/product/tpl-series/) — eight front-terminal
  industrial and telecommunications models;
- [MSV](https://csb-battery.com/product/msv-series/) — seven 2 V stationary
  cells;
- [MU](https://csb-battery.com/product/mu-series/) — four 2 V high-capacity
  stationary cells;
- [RE](https://csb-battery.com/product/re-series/) — two 2 V lead-carbon
  renewable-energy models.

The candidate set was reduced before import by both exact normalized MPN and
hidden manufacturer/model-token checks against existing names. This excluded
official models already represented by legacy records whose structured MPN
field is empty. The final 24 candidates passed the independent description and
preview gates.

Database and API verification found 24 published cards, 24 distinct MPNs and
24 distinct canonical preview paths. Every card remains `noindex` and
`on_request`, has a null price, and emits no commercial `Offer`. The complete
products table contains zero duplicate non-null normalized MPN groups after
the import. No manufacturer image was copied because a storefront reuse grant
was not established.
