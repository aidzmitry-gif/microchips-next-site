# RB UPS and traction content wave 108 — 2026-07-28

## Scope

This loop continued from the verified wave-107 state. It processed seven new
1C products in the UPS, UPS-battery and traction-battery scope. Electronic
components, previously completed products and unresolved duplicate clusters
were excluded.

Before any write, the exact `КА` / `ФР` identifiers were checked against both
`one_c_nomenclature_items` and the RB `site_products` rows. All seven products
were unpublished, had `on_request` availability, no price and no previous
source-backed description.

## Applied content

| 1C external ID | Manufacturer | MPN | Verified facts |
| --- | --- | --- | --- |
| `КА-00004889` | CyberPower | `UT2200EG` | line-interactive UPS; 2200 VA / 1320 W; 167–295 V input range; simulated sine wave; four Schuko outputs; typical 4 ms transfer |
| `ФР-00001011` | TAB | `215180` | Golf Cart GEL traction battery; 6 V; 235 Ah C100 / 210 Ah C20 / 180 Ah C5; 244 × 190 × 255/276 mm; 30.9 kg |
| `КА-00005755` | IPPON | `Innova TB 1000` | online double-conversion UPS; 1000 VA / 900 W; pure sine; four IEC C13 outputs; 2 × 12 V 9 Ah batteries |
| `КА-00003995` | IPPON | `Back Basic 1050 Euro` | line-interactive UPS; 1050 VA / 600 W; 162–275 V input; modified sine; two EURO outputs; 1 × 12 V 9 Ah battery |
| `КА-00005606` | OMRON | `S8BA-24D24D480SBF` | separated-battery DC UPS control unit; 24 V DC; 20 A / 480 W; uninterrupted switching; S8BA-S480L battery module is required separately |
| `КА-00003351` | APC | `RBC11` | lead-acid replacement battery cartridge; 12 V; 17 Ah; for compatible APC Smart-UPS models |
| `КА-00004378` | Ventura | `VTG 12 080 XT` | TRUE GEL traction/stationary battery; 12 V; 71 Ah C5 / 74 Ah C10 / 80 Ah C20; 254 × 168 × 203 mm; 25 kg |

Manufacturer evidence:

- CyberPower exact product page:
  `https://www.cyberpower.com/global/en/product/sku/ut2200eg`;
- TAB official Small Traction & Leisure catalogue:
  `https://www.tabitalia.com/public/documenti/TAB%20Small%20Traction%26Leisure.pdf`;
- IPPON exact product pages:
  `https://ippon.ru/catalog/item/ippon-1000-2050420/` and
  `https://ippon.ru/catalog/item/ippon-1050-Euro-403409/`;
- OMRON S8BA catalogue and current specification page:
  `https://www.ia.omron.com/data_pdf/cat/s8ba_u701-e1_4_9_csm1042516.pdf?id=3450` and
  `https://www.ia.omron.com/products/family/3450/specification.html`;
- Schneider Electric / APC exact RBC11 page:
  `https://www.se.com/us/en/product/RBC11/apc-replacement-battery-cartridge-11-with-2-year-warranty/`;
- Ventura official industrial catalogue and series page:
  `https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf` and
  `https://ventura-battery.ru/produktsiya/`.

The malformed 1C separator in `Back Basic 1050¶Euro` was normalized only in
the storefront display name after exact model confirmation. No local warranty,
stock or price was inferred. The OMRON copy explicitly says that the battery
module is separate; it does not present the module as included with the
control unit.

All seven products were published only as `noindex, nofollow` previews in
their existing verified categories. No category outside UPS or industrial
batteries was created or used.

## Duplicate and media decisions

- Each new normalized `manufacturer + MPN` pair occurs exactly once in the
  canonical `products` table after the wave.
- `КА-00003995` was used for IPPON Back Basic 1050 Euro; the same numeric
  suffix was not silently substituted with an `ФР` identifier.
- The Inelt Gamma 3K archive image remained on hold: it is linked to one
  Bitrix product, but the visible chassis does not expose the exact MPN and a
  primary exact-model content source was not found in this loop.
- No unverified external image was imported. Consequently, all seven new
  cards correctly retain the image placeholder and do not count as strict
  content-plus-media complete.

## Price policy

The accepted price policy remains:

1. a current legacy-site price keeps multiplier `1`;
2. otherwise a usable current 1C source price is multiplied exactly once by
   `2` and the original value, multiplier and provenance are retained;
3. without either source the storefront shows `Цена по запросу`.

The current 1C inventory snapshot has **0** rows with the complete usable
price/currency/price-type evidence required by the importer. Therefore no
price was invented or derived in this wave.

## Applied counters

- RB site products: 7,143;
- published noindex previews: 98 (`+7`);
- applied source-backed descriptions: 221 (`+7`);
- verified published media products: 40 (`+0`);
- current prices with provenance evidence: 57 (`+0`);
- strict non-electronic content-complete cards: **40 / 7,286 = 0.55%**;
- remaining fixed first-10% enrichment queue: 689 records.

The strict completion count did not increase because these seven products
still need source-authorized, visually verified media. Description coverage
improved, but it is not reported as full-card completion.

## Verification

- manifest validation: seven description rows and seven preview rows, equal
  ID sets, zero repeated IDs, zero repeated slugs, zero electronic categories;
- description dry-run: seven valid drafts; apply: seven descriptions;
- preview dry-run and apply: seven products, zero indexable URLs, zero offers,
  zero verified-priced products;
- repeat description staging: zero created, seven unchanged;
- repeat preview dry-run: seven products, zero indexable URLs and zero offers;
- normalized `manufacturer + MPN` database check: seven groups, one product
  in every group;
- browser SSR for all seven pages: HTTP-rendered product state, one H1,
  canonical path equal to the requested product path, `noindex, nofollow`,
  `Цена по запросу`, no `Offer` schema, no 404 and no horizontal overflow;
- two model-specific technical facts per page were confirmed in the rendered
  body; all seven pages expose the explicit image placeholder;
- SEO audit: 115 checked URLs, zero blocking issues;
- enrichment queue rebuilt with fixed baseline 7,286 and
  `seo:electronic-components` excluded: 40 complete, 689 remaining.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-108-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-108-2026-07-28.json`
- `docs/audits/generated/rb-enrichment-queue-wave-108.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-108.summary.json`
