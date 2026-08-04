# RB Cameron Sino media and duplicate waves 99–100 — 2026-07-28

## Scope

This loop continued from the verified wave-98 state. It did not repeat prior
identity, taxonomy, content, media or duplicate decisions.

- only products present in the 1C inventory were considered;
- electronic components remained excluded;
- exact Bitrix-to-1C name identity and a readable physical model label were
  required before a legacy image could be published;
- a compatible battery was not represented as an OEM Zebra product;
- the duplicate scan covered the next enrichment priorities 351–550;
- price, stock, warranty and indexability were not inferred.

## Exact product and media result

One new product passed all strict identity and media gates:

| Field | Verified value |
| --- | --- |
| 1C external ID | `КА-00006847` |
| Bitrix element | `12406` |
| Manufacturer | Cameron Sino |
| MPN | `CS-ZDS360BL` |
| Technology | Li-ion |
| Voltage | 3.7 V |
| Capacity | 2200 mAh |
| Energy | 8.14 Wh |
| Replacement references | `BTRY-36IAB0E-00`, `82-166537-01` |
| Media SHA-256 | `359fa4814e4039391df78f11abf94b78defb8500ad0f30f999acdc7034b1193e` |

The electrical values and exact MPN are legible on the company-owned legacy
Bitrix image. The Cameron Sino regional catalogue independently lists the same
MPN, values and compatible Zebra scanner family. The safe product name says
“compatible battery”; Zebra is not stored as the manufacturer and no OEM or
original-product claim is made.

The page was published only as a `noindex, nofollow` preview at:

`/catalog/replacement-batteries/cameron-sino-cs-zds360bl`

It remains `on_request`, shows “Цена по запросу” and emits no `Offer` schema.

Rejected legacy assets remained rejected when the label could not prove an
exact SKU/MPN. The wave deliberately did not enlarge the candidate set through
signature or capacity-only matching.

## Duplicate result

Ten non-public RB site links were excluded across eight exact-model clusters:

- two duplicate ROBITON Ecocharger AK02 rows;
- one duplicate RADIAN V-mount 2СН row;
- one duplicate ROBITON LAC612-1000 row;
- two duplicate СОНАР УЗ 207.03 rows;
- one duplicate Camelion BC-0906SM Titan row;
- one duplicate Camelion BC-1010B row with Cyrillic/Latin `В/B` variation;
- one duplicate ROBITON Smart4 9V base row;
- one duplicate ROBITON Smart4 9V adapter-bundle row.

The exclusion command removed only unpublished `microchips-by` links. It did
not delete canonical products, other market links or published URLs. A final
database query confirmed zero remaining RB links for all ten excluded IDs.

The following candidates remain held because the available evidence does not
prove equivalence: ROBITON ProCharger1000 display variants, Smart4 9V Pro,
HOTA D6 Pro versus D6 Pro BO, generic LiFePO4 chargers without manufacturer or
MPN, and connector-specific IR12-2000S records.

## Verified counters

- RB site products: 7,145;
- published noindex previews: 76;
- applied source-backed descriptions: 199;
- current prices with provenance evidence: 57;
- verified published media products: 33;
- strict non-electronic content-complete cards: **33 / 7,286 = 0.45%**;
- remaining fixed first-10% queue: 696 records.

The strict percentage increased because this product has identity, category,
description, safe commercial state and verified published media together. It
is a real improvement, but it is not reported as a false +10 percentage-point
milestone.

The current 1C snapshot still contains zero usable price/currency/price-type
rows. The established fallback remains `1C source_price × 2`, but no value was
fabricated for this product.

## Verification

- description staging, description application, preview publication, media
  import and duplicate exclusion all passed dry-run before apply;
- repeat dry-run: description `1 unchanged`, media `1 unchanged`, preview valid;
- browser desktop and 390 px mobile checks: one H1, one verified product image,
  no horizontal overflow and no browser console errors;
- SEO metadata: self-canonical path, `noindex, nofollow`, zero `Offer` schema;
- SEO release audit: 92 checked URLs, 0 blocking issues;
- enrichment queue rebuilt with fixed baseline 7,286 and electronic-component
  exclusion: 33 complete, 696 remaining to the first 10% target;
- all four HTML prototypes passed `scripts/verify-rb-prototype.ps1`.

No PHP or TypeScript source changed in this wave. Validation ran through the
production Laravel commands and the live Next.js runtime.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-99-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-99-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-99-2026-07-28.json`
- `docs/imports/rb-strict-duplicate-exclusion-wave-100.csv`

