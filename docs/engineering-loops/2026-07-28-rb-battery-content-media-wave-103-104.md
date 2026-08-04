# RB battery content and exact-label media waves 103–104 — 2026-07-28

## Scope

This loop continued from the verified wave-102 state. It processed only
products present in the 1C inventory and excluded electronic components.
Previous description, media and duplicate decisions were not repeated.

The wave added source-backed content for six exact battery models, published
all six only as `noindex, nofollow` previews, and admitted two company-owned
legacy images whose physical labels visibly prove the exact MPN.

## Source-backed content result

| 1C external ID | Manufacturer | Exact MPN | Primary evidence |
| --- | --- | --- | --- |
| `КА-00003094` | B.B. Battery | `BPS28-12` | B.B. Battery manufacturer product page |
| `ФР-00001851` | B.B. Battery | `FTB100-12` | B.B. Battery manufacturer product page |
| `КА-00001923` | B.B. Battery | `HRL5.5-12` | B.B. Battery manufacturer product page |
| `ФР-00002258` | CSB Energy Technology | `UPS122406` | official CSB 2026 datasheet |
| `КА-00002966` | B.B. Battery | `HRC5.5-12` | B.B. Battery 2025 product booklet plus exact physical label |
| `ФР-00001994` | Delta | `HR 12-24 W` | official Delta product page plus exact physical label |

Only facts tied to the exact model were copied. The FTB100-12 capacity is
stored with its stated 8-hour rate; the CSB watt values retain the documented
discharge time, end voltage and temperature. No price, stock or local warranty
was inferred.

## Exact-label media result

Two archived assets passed the strict `visible_exact_mpn` gate:

| Product | Bitrix element | Visible evidence | SHA-256 |
| --- | ---: | --- | --- |
| B.B. Battery HRC5.5-12 | `1618` | `B.B. BATTERY HRC5.5-12`, VRLA label, Microchips watermark | `79492e87157fe2a3ff0602f973c46614322f04b4c1ce1cfbc4fbe98d5247f03f` |
| Delta HR 12-24W | `3110` | `DELTA HR 12-24W`, `12V 6Ah`, AGM/VRLA label, Microchips watermark | `34bf50587da07b1d76e474f9169c81e7acfb676f495a5bbf618aad803ec03ffe` |

The Delta investigation caught an important prefix collision before apply:
`КА-00001994` is an unrelated orange office marker, while the battery is
`ФР-00001994`. The media and description manifests use only the verified
`ФР` product. The office-marker record was not changed or linked to the image.

Other inspected assets remained rejected when the model was ambiguous, the
manufacturer differed, or Bitrix contained more than one plausible variant.

## Duplicate result

No new duplicate exclusion was applied. The deterministic first-10% queue has
691 remaining rows and its whole earlier 693-row span was already covered by
the duplicate scans in waves 95–102. A fresh database check found zero active
RB duplicate groups by exact normalized manufacturer plus MPN. Rescanning or
recreating an old exclusion registry would have violated the no-repeat rule.

## Applied counters

- RB site products: 7,145;
- published noindex previews: 85;
- applied source-backed descriptions: 208;
- verified published media products: 38;
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **38 / 7,286 = 0.52%**;
- remaining fixed first-10% enrichment queue: 691 records.

The accepted price rule remains: legacy-site price unchanged, otherwise a
usable 1C source price multiplied once by two. The current 1C snapshot still
has zero usable price rows, so these six pages correctly show price on request.

## Verification

- initial description dry-run: 6 valid records;
- description apply: 6 applied, no commercial fields changed;
- preview dry-run and apply: 6 products, 0 indexable URLs, 0 offers;
- media dry-run and apply: 2 verified imports and 2 published images;
- repeat staging: `0 created, 6 unchanged`;
- repeat media dry-run: `0 imported, 2 unchanged`;
- live SSR check for all six pages: one H1, self-canonical, `noindex,
  nofollow`, price-on-request state, no horizontal overflow and no `Offer`
  schema;
- exact-label pages expose one verified image each; the other four correctly
  expose no unverified image;
- SEO audit: 101 checked URLs, 0 blocking issues;
- enrichment queue rebuilt with fixed baseline 7,286 and electronic-component
  exclusion: 38 complete, 691 remaining.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-103-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-103-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-103-2026-07-28.json`

