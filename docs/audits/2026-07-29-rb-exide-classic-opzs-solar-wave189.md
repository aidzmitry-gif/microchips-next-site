# RB Exide Classic OPzS Solar expansion — wave 189

Date: 2026-07-29. Site: `microchips-by`.

## Result and primary source

Twenty-one exact filled-and-charged Exide Classic OPzS Solar 2 V cell
identities absent from PostgreSQL and earlier expansion waves were added from
the current manufacturer datasheet:

`https://www.exidegroup.com/en/document/classic-opzs-solar-datasheet`

The first draft contained 20 models. Adversarial source reconciliation found
that the official 2 V table has 21 wet variants, so `NVSL024600WC0FA` / OPzS
Solar 4600 was added before import. The separate 6 V and 12 V `NVZS...` blocks
and inferred dry-charged `D` variants were deliberately excluded.

Each card preserves the long manufacturer part number as the exact MPN while
using the readable `OPzS Solar <capacity>` type in its display name. Capacity
is qualified as C120 to 1.85 V per cell at 25 °C. Dimensions, installed length
and filled-cell mass remain separate fields; the source's vent-height and
mass-tolerance qualifications are retained.

## Identity and taxonomy boundary

- identity: exact `manufacturer=Exide` plus exact `NVSL...W...` MPN;
- category: `catalog/industrial-batteries/batteries-industrial`;
- technology: flooded lead-acid OPzS with tubular positive plates;
- no cross-manufacturer collapse against LEOCH OPzS products;
- no inferred dry version, local stock, compatibility, warranty or price;
- no image because a reusable exact-SKU asset and rights basis were not
  established.

## Commercial boundary

- availability: `on_request`;
- price and price evidence: absent;
- indexability: false;
- `Offer` schema: absent.

## Verification

- Generator tests: 3/3 passed, including the exact-MPN/readable-label split.
- Candidate dry-run/apply: 21 createable / 21 created, zero unchanged.
- Description stage/apply and preview dry-run/apply: 21/21 accepted.
- Reusable verifier: 21 products, 21 distinct paths, zero price evidence,
  zero duplicate normalized MPN groups, no errors.
- API query `q=OPzS Solar`: 21 Exide results and 21 distinct paths.
- Industrial + Exide + 4600 Ah filter: exactly `NVSL024600WC0FA` after adding
  explicit C120 facet support and incrementing the facet cache schema.
- OPzS Solar 4600 storefront: HTTP 200, exact MPN and capacity, `noindex`, no
  `Offer` schema.
- Final totals: 16,713 published RB market rows / 16,712 canonical cards;
  4,234 published broad B2B rows / 4,233 canonical cards; 1,064 industrial
  battery rows.
- SEO audit: PASS across 16,750 routes and seven redirects, zero blockers.

All four wave artifacts use `exide-wave189-2026-07-29` under `docs/imports/`.
