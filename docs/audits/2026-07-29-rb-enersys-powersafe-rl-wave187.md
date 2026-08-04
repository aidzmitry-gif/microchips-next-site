# RB EnerSys PowerSafe RL expansion — wave 187

Date: 2026-07-29. Site: `microchips-by`.

## Result

Twenty-three exact PowerSafe RL Ni-Cd identities were added to the industrial
battery category. The range is still exposed by the current EnerSys product
page, and the linked manufacturer range table provides exact five-hour
capacity, dimensions and unpacked mass:

- current page: `https://www.enersys.com/en/products/batteries/powersafe/powersafe-rl/`;
- model table: `https://www.enersys.com/493c0d/globalassets/documents/product-documentation/powersafe/nicd/amer/US-RL-RS-003_0114.pdf`.

`RL 40` and `RL 55` were excluded because nearby HRL model strings created an
avoidable identity risk. RL was not merged with HRL.

## Holds and commercial boundary

- The model table is dated 2014 but remains linked from the active manufacturer
  page; specification currency requires vendor confirmation before indexation.
- Current first-party surfaces conflict between 1.2 V and 2 V. Voltage was
  omitted from the cards rather than inferred.
- All records are `on_request`, price null and noindex; no `Offer` or image was
  created.

## Verification

- Candidate and content/preview gates: 23/23 accepted.
- Reusable verifier: 23 products, 23 paths, zero price evidence, zero duplicate
  normalized MPN groups, passed.
- API `q=PowerSafe RL`: 23 cards, 23 paths, zero numeric prices.
- All artifacts use `enersys-wave187-2026-07-29` under `docs/imports/`.
