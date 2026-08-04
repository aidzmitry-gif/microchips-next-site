# RB priced preview and content waves 93–94 — 2026-07-28

## Scope and commercial rule

This loop continued from the verified wave-92 state and did not repeat the
completed 1C inventory, taxonomy or broad duplicate scans.

- only products present in the 1C inventory were processed;
- `seo:electronic-components` remained excluded;
- the legacy Microchips price wins when it exists;
- when no legacy price exists, a current 1C price is eligible only as
  `source_price × 2` with exact product identity, currency, price type,
  observation date and source reference preserved;
- price never implies stock; availability remains `on_request`;
- a priced noindex preview requires an explicit manifest opt-in and matching
  current price evidence. The command fails closed otherwise.

The loaded 1C snapshot still exposes zero usable price/currency/price-type
values. Therefore no `one_c_x2` value was fabricated or applied in these
waves; all four newly applied prices came from the legacy site.

## Identity, price and preview result

Four exact Delta pairs passed the evidence review and received legacy-site
price evidence:

| 1C external ID | Model | Preview category |
| --- | --- | --- |
| `КА-00003468` | Delta DTM1226 | batteries for UPS |
| `КА-00002817` | Delta DT1233 | batteries for UPS |
| `КА-00003766` | Delta CGD1208 | industrial batteries |
| `КА-00003445` | Delta CGD1233 | industrial batteries |

All four are published as HTTP 200 `noindex` previews with `on_request`
availability. Their visible prices have current provenance evidence, but no
`Offer` schema was emitted because local stock/offer facts are not confirmed.

The preview command now permits a non-null price only when
`allow_verified_price=true` is present and a matching current evidence row
exists. Tests prove that a missing opt-in and mismatched evidence both block
publication.

## Source-backed content result

Twelve descriptions were applied from exact manufacturer sources:

- Delta DTM1226, DT1233, CGD1208 and CGD1233;
- CSB GPL1272 and HRL1225W;
- Sonnenschein A606/200 (`NGA6060200HS0FC`);
- MEAN WELL EDR-150-24, LRS-50-5, NDR-480-24, SE-450-12 and HDR-60-12.

The latter eight received unique HTTP 200 `noindex` previews. They have no
verified price in either eligible source, so the storefront correctly renders
“Цена по запросу” rather than inventing a number.

## Duplicate and media adversarial checks

Ten repeated-model clusters were reviewed. Terminal type, revision, package
quantity or incomplete identity evidence made every cluster unsafe for an
automatic merge. They remain unpublished drafts; no false duplicate was
deleted and no duplicate page was created.

The legacy-media pass found no additional exact-model image whose visible
label proved identity. Ambiguous images remain blocked. This keeps the strict
content-complete count unchanged even though twelve descriptions and twelve
preview pages were added.

## Verified counters after waves 93–94

- RB site products: 7,163;
- published noindex previews: 49;
- current site prices with evidence: 57;
- approved identity candidates: 58; pending: 50; rejected: 1;
- applied source-backed descriptions: 172;
- storefront-ready verified media: 32;
- strict non-electronic content-complete cards: **32 / 7,286 = 0.44%**;
- remaining cards in the fixed first-10% queue: 697.

This loop adds useful and verified storefront coverage, but it is not a false
`+10%` milestone. The strict denominator requires description, identity,
category, commercial state and verified media together.

## Verification

- targeted PHPUnit: 31 tests, 189 assertions, all passed;
- SEO audit: 62 checked URLs, 0 blocking issues;
- priced Delta page: HTTP 200, `noindex`, `181.00 BYN`, `on_request`, no
  `Offer` schema;
- unpriced MEAN WELL page: HTTP 200, `noindex`, “Цена по запросу”,
  `on_request`, no `Offer` schema;
- enrichment queue rebuilt with fixed baseline 7,286 and electronic-components
  exclusion: 697 records, no denominator drift;
- all four HTML prototypes passed `scripts/verify-rb-prototype.ps1`.

## Reproducible evidence

- `docs/imports/rb-ready-mpn-evidence-decisions-wave-93.json`
- `docs/imports/rb-price-evidence-wave-93.csv`
- `docs/imports/rb-source-backed-description-drafts-wave-93-2026-07-28.json`
- `docs/imports/rb-source-backed-description-drafts-wave-94-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-93-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-94-2026-07-28.json`

