# RB EnerSys PowerSafe VGM expansion — wave 184

Date: 2026-07-29. Site: `microchips-by`.

## Result

Twenty-five exact PowerSafe VGM model identities absent from the catalogue
were created, enriched and published as safe noindex previews under
`catalog/industrial-batteries/batteries-industrial`.

Primary source:

`https://www.enersys.com/4ab530/globalassets/documents/product-documentation/powersafe/vgm/amer/en-rs-amer-ps-vgm.pdf`

The official EnerSys document is dated 2024 and provides exact battery type,
five-hour capacity to 1.15 V/cell at 20 °C, dimensions and typical mass. Shared
facts are limited to the same document's valve-regulated Ni-Cd pocket-plate
construction, top terminals, 30–120 minute discharge range, gas recombination
statement and operating-temperature range.

## Adversarial source decision

A separate current EnerSys webpage exposes a 2 V technical field, while an
official power-and-utilities guide describes VGM as 1.2 V. Because those two
first-party surfaces conflict, nominal voltage was not added to any VGM card.
No value was inferred from chemistry or neighbouring product lines. This hold
does not affect the exact model identity, capacity, dimensions or mass taken
from the model-level range table.

## Safe commercial boundary

- all 25 records are `on_request`;
- all numeric prices are null;
- no price-evidence or `Offer` records were created;
- all canonical product URLs remain `noindex`;
- no image was copied because reusable image rights were not established.

## Artifacts

- `docs/imports/rb-manufacturer-series-enersys-wave184-source.json`
- `docs/imports/rb-manufacturer-product-candidates-enersys-wave184-2026-07-29.json`
- `docs/imports/rb-source-backed-description-drafts-enersys-wave184-2026-07-29.json`
- `docs/imports/rb-source-verified-preview-enersys-wave184-2026-07-29.json`

## Verification

- Candidate dry-run/apply: 25 createable/created, zero unchanged or collisions.
- Description stage/apply and preview dry-run/apply: 25/25 accepted.
- Reusable wave verifier: 25 products, 25 distinct paths, zero price evidence,
  zero duplicate normalized MPN groups, zero errors, passed.
- API `q=VGM`: 25 products, 25 paths, zero numeric prices.
- Filter EnerSys + documented Ni-Cd technology + 400 Ah: exactly VGM 400.
- VGM 400 storefront: HTTP 200, exact name/capacity, `noindex`, no `Offer`.
- Current totals: 16,615 published RB market rows, 16,614 canonical visible
  cards; 4,136 published B2B rows, 4,135 canonical B2B cards; 976 industrial
  battery cards.
- SEO release audit: PASS across 16,652 routes and seven redirects, zero
  blockers. The sitemap remains empty because these preview URLs are noindex.
