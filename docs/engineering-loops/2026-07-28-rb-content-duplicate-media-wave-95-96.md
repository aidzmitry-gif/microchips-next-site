# RB content, duplicate and media waves 95–96 — 2026-07-28

## Scope

This loop continued from waves 93–94 without repeating the inventory,
taxonomy or previously reviewed duplicate clusters.

- only products present in the 1C inventory were processed;
- `seo:electronic-components` remained excluded;
- descriptions use exact primary manufacturer sources;
- legacy-site price remains preferred where already evidenced; a usable 1C
  price is calculated as `source_price × 2` with its audit fields preserved;
- no price implies “Цена по запросу”, never a fabricated zero or offer;
- media remains non-public until exact-model, hash, rights and visual gates all
  pass.

## Source-backed catalogue result

Fourteen unique 1C products received applied descriptions and unique HTTP 200
`noindex` previews:

- CyberPower OLS1000ERT2UA, PR750ELCD and UT1100EG;
- APC Smart-UPS SMT3000IC;
- Eaton 9E1000I;
- MEAN WELL IRM-15-12, IRM-30-24, LRS-350-24, UHP-500-24, DDR-120D-24,
  HDR-30-12, RSD-300F-12 and SD-350C-24;
- Phoenix Contact QUINT 2938646.

The Phoenix Contact page explicitly preserves the discontinued lifecycle state
and manufacturer replacement `2904623`; the card does not misrepresent it as a
current stocked product.

All fourteen have `on_request` availability, no unverified price and no
`Offer` schema. Their categories are limited to UPS systems, power supplies or
power converters.

## Duplicate result

The next 150 non-electronic queue rows were checked without repeating the ten
clusters from the preceding audit.

- `КА-00005685` was removed from the RB site profile as an exact duplicate of
  `ФР-00001952` B.B. Battery BPS 26-12;
- `КА-00005151` FANSO ER14505H/S and `КА-00006413` FANSO
  ER26500H-LD/EHR-02 were confirmed exact duplicates, but were already absent
  from the RB site profile, so no second mutation was attempted;
- APC SURT192RMXLBP, ROBITON EN3000S/5-24, SAFT LS17500, SAFT LS26500 E-STD
  and TEKCELL connector variants remain held because terminal, country,
  package or malformed-model evidence is contradictory.

No shared canonical product or other country profile was deleted.

## Media result and new safety gate

Twelve exact models from waves 93–94 were visually reviewed against official
manufacturer pages/documents.

- seven images/documents prove the exact model technically;
- five were rejected because the asset was corrupt, blocked, series-only or
  visibly showed a different suffix;
- three direct Delta raster images were staged as non-public pending records;
- no official source disclosed a clear commercial-copy licence, therefore no
  candidate was published.

The backend now has `media:import-verified-source-images`. It can promote a
reviewed official-source candidate only when all of the following are present
and consistent: published regional product, exact normalized MPN, HTTPS source
page and asset URL, local supported raster, SHA-256, explicit rights basis and
visual verification note. Missing rights evidence and identity mismatch fail
closed. The command is installed in the rebuilt backend and worker images.

## Verified counters

- RB site products: 7,162;
- published noindex previews: 63;
- current site prices with evidence: 57;
- applied source-backed descriptions: 186;
- verified published media products: 32;
- pending non-public media candidates: 8;
- strict non-electronic content-complete cards: **32 / 7,286 = 0.44%**;
- fixed first-10% queue: 697 records.

The strict percentage does not increase because this gate requires verified
published media in addition to identity, category and content. The loop still
adds 14 useful pages and removes one confirmed duplicate; it is not reported as
a false `+10%` milestone.

## Verification

- targeted PHPUnit: 44 tests, 251 assertions, all passed;
- Laravel Pint: new command and tests passed;
- SEO audit: 77 checked URLs, 0 blocking issues;
- CyberPower OLS1000ERT2UA page: HTTP 200, exact model, `noindex`,
  “Цена по запросу”, `on_request`, no `Offer` schema;
- all four HTML prototypes passed `scripts/verify-rb-prototype.ps1`;
- rebuilt backend and worker containers are healthy;
- the new verified-source media command is registered in the production image.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-95-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-95-2026-07-28.json`
- `docs/imports/rb-strict-duplicate-exclusion-wave-96.csv`
- `docs/imports/rb-strict-duplicate-exclusion-wave-96-current.csv`
- `docs/imports/rb-source-image-candidates-wave-95-2026-07-28.json`

