# RB category content, ROBITON and duplicate waves 97–98 — 2026-07-28

## Scope

This loop continued after wave 96 and did not repeat earlier catalogue,
identity, duplicate or content batches.

- only 1C products were considered;
- electronic components remained excluded;
- the next duplicate scan covered enrichment priorities 151–350, not the
  previously checked first 150 rows;
- exact manufacturer pages were required for product facts;
- category content was added only to existing noindex previews;
- no image, price, availability or indexation claim was inferred.

## Category-content result

The published category audit found eight noindex sections with titles but no
market-specific introduction. The charger section became published by the new
ROBITON preview wave, so nine sections were enriched in total:

- industrial batteries parent, UPS batteries and industrial batteries;
- power systems parent, power supplies, power converters and UPS systems;
- chargers;
- primary cells.

`content:import-site-category-content` now imports these texts with fail-closed
checks. It requires a published regional category, matching locale, an existing
category URL, matching canonical path and both URL/SEO records to remain
noindex. It updates only title and description and cannot enable indexation.

The Next.js category hero now renders this reviewed per-category description
instead of a generic battery paragraph on every section. The production build
and SSR runtime both confirm the new content.

## Source-backed product result

Twelve unique ROBITON chargers received exact-source descriptions and HTTP 200
noindex previews:

- Li-1, Li-2 and Li-4 Plus;
- MasterCharger 1B USB, MasterCharger 4T5 Pro and MasterCharger Pro;
- MultiCharger LCD2 and MultiCharger2;
- Smart 2, Smart4 C3, SmartCharger/IV and SmartDisplay 1000.

Second 1C rows for ProCharger1000 and Smart4 C3 were deliberately not selected
as new content targets. All twelve published pages remain `on_request`, show
“Цена по запросу” and emit no `Offer` schema.

## Duplicate result

Seven non-public RB draft links were removed after exact-model/specification
comparison:

- two duplicate NAKI `321162.221 / 24×4PzS460` rows;
- one QJ5003C III row;
- one Longwei LW-K3010D row;
- one NICE-Power R-SPS3010 row;
- one ROBITON SN500S row;
- one APC APCRBC11 row.

APCRBC141, Gamma IN3000RM-GA-1, CSB UPS12240 6 F2, ROBITON IR12-2000S and
ROBITON USB1000 white remain held because legacy confidence, connector,
`Slim`, URL or device-type evidence is materially ambiguous. No canonical
product, public URL or other market profile was deleted.

## Media adversarial result

The fourteen wave-95 products were checked against official manufacturer
pages and PDFs. No image passed both requirements:

1. exact model suffix is visibly proven on the asset; and
2. commercial reuse rights are explicit.

Representative or series images from CyberPower, APC, Eaton, MEAN WELL and
Phoenix Contact were rejected. The storefront correctly retains placeholders.

## Verified counters

- RB site products: 7,155;
- published noindex previews: 75;
- applied source-backed descriptions: 198;
- current prices with evidence: 57;
- verified published media products: 32;
- categories with reviewed descriptions: 9;
- strict non-electronic content-complete cards: **32 / 7,286 = 0.44%**;
- remaining fixed first-10% queue: 697 records.

The strict percentage remains unchanged because verified media is still the
completion gate. This loop adds twelve useful product pages, nine useful
category introductions and removes seven duplicates, but is not reported as a
false ten-percentage-point milestone.

## Verification

- targeted PHPUnit: 45 tests, 255 assertions, all passed;
- category Vitest: 7 tests, all passed;
- production Next.js 16.2.10 build passed;
- SEO audit: 90 checked URLs, 0 blocking issues;
- `/catalog/chargers`: HTTP 200, reviewed charger introduction, `noindex`;
- `/catalog/chargers/robiton-li-2`: HTTP 200, exact model, `noindex`, price on
  request, no `Offer` schema;
- backend, worker and frontend containers are healthy;
- all four HTML prototypes passed `scripts/verify-rb-prototype.ps1`.

## Reproducible evidence

- `docs/imports/rb-site-category-content-wave-97-2026-07-28.json`
- `docs/imports/rb-source-backed-description-drafts-wave-97-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-97-2026-07-28.json`
- `docs/imports/rb-strict-duplicate-exclusion-wave-98.csv`

