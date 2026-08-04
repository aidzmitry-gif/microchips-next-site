# RB industrial-battery content and media wave 107 — 2026-07-28

## Scope

This loop continued from the verified wave-106 queue and processed only new
1C inventory products outside the electronic-component scope. Previously
resolved products, stale queue rows and known duplicate clusters were not
reapplied.

## Applied content

Four exact products passed source, identity and regional-link checks:

| 1C external ID | Manufacturer | MPN | Verified facts |
| --- | --- | --- | --- |
| `КА-00004769` | Ventura | `GT 06 270` | traction VRLA AGM battery; 6 V; 282 Ah C5; 334 Ah C20; 295 × 178 × 360 mm; 47 kg; AM terminal |
| `КА-00005166` | B.B. Battery | `UPS 12220W` | high-rate VRLA AGM battery; 12 V; 1320 W/block at the stated 15-minute discharge basis; 228 × 139 × 200 mm; 17.8 kg |
| `ФР-00002343` | CSB | `UPS123606` | high-rate VRLA AGM battery; 12 V; 360 W at 5 minutes to 9.60 V/block; F2/F1 option; 150.9 × 51.0 × 98.6 mm; 1.97 kg |
| `КА-00005195` | EnerSys | `X Cell` | Cyclon thin-plate-pure-lead AGM cell; physical label confirms 2 V and 5.0 Ah |

Manufacturer evidence:

- Ventura official industrial catalogue:
  `https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf`;
- B.B. Battery official regional UPS series page:
  `https://www.bb-battery.ru/products/ups/`;
- CSB official UPS123606 datasheet:
  `https://csb-battery.com/wp-content/uploads/2024/07/CSB-Datasheet-UPS123606-%E2%80%93-053124.pdf`;
- EnerSys official Cyclon series page:
  `https://www.enersys.com/en-gb/products/batteries/cyclon/cyclon/`.

The unsupported `53 Ah` text from the 1C name of UPS12220W and the unsupported
`7.5 Ah` text from the 1C name of UPS123606 were deliberately not published:
the current manufacturer documents rate these exact products by short-duration
power. No local warranty, stock or price was inferred.

All four products were published only as `noindex, nofollow` previews. Ventura
GT 06 270 was moved from the generic UPS category to the verified traction
battery category; the other three remained in their verified industrial/UPS
sections.

## Verified media

One company-owned Bitrix asset passed the stricter tier-B identity gate:

- product: `КА-00005195` EnerSys Cyclon X Cell;
- Bitrix element: `742`;
- archive member:
  `_shared/upload/iblock/e2c/snrwhquxtr0olsg734yecvtzetq39aul.jpg`;
- visible label: `EnerSys`, `Cyclon`, `2 VOLT 5.0 AH X CELL`;
- Microchips watermark: present;
- SHA-256:
  `f564a165172a4106cdbef8c39df1b6d9fcd3fa603cdc134c8d660131eb4244e1`.

The image is explicitly classified as
`unique_catalog_identity_plus_visual_consistency`: no separate alphanumeric
MPN is visible or claimed.

## Adversarial exclusions

- Ventura FT 12-200 and GPL 12-75 remain excluded from this wave because each
  belongs to an unresolved or already-canonical duplicate cluster.
- Ventura GPL 12-20 is held because the current official model list does not
  provide the exact product evidence needed for publication.
- APC RBC123/RBC140/RBC152 and SURT192RMXLBP-CH remain held where the 1C text
  conflicts with, or is less specific than, current cartridge documentation.
- CSB GP12170B1 remains held because the exact suffix/capacity evidence is not
  unambiguous.
- Kijo `6-EVG-100` was not rewritten from the official `6-EVF-100` evidence:
  the one-letter model difference is material.
- Prefix review confirmed that `ФР-00002343`, not an equal-number `КА` item,
  is the CSB UPS123606 product.

## Applied counters

- RB site products: 7,143;
- published noindex previews: 91;
- applied source-backed descriptions: 214;
- verified published media products: 40;
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **40 / 7,286 = 0.55%**;
- remaining fixed first-10% enrichment queue: 689 records.

The accepted price policy remains legacy-site price first, otherwise a usable
1C source price multiplied exactly once by two. The loaded 1C snapshot still
contains no usable price rows, so no price was invented in this wave.

## Verification

- description dry-run: four valid drafts; apply: four descriptions;
- preview dry-run and apply: four products, zero indexable URLs, zero offers;
- media dry-run and apply: one tier-B asset imported and published;
- repeat description staging: zero created, four unchanged;
- repeat media dry-run: zero imported, one unchanged;
- browser SSR for all four pages: one H1, self-canonical, `noindex, nofollow`,
  price-on-request state, no `Offer` schema and no horizontal overflow;
- EnerSys page exposes one verified image; the other three expose no
  unverified image;
- SEO audit: 108 checked URLs, zero blocking issues;
- enrichment queue rebuilt with fixed baseline 7,286 and
  `seo:electronic-components` excluded: 40 complete, 689 remaining.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-107-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-107-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-107-2026-07-28.json`
- `docs/audits/generated/rb-enrichment-queue-wave-107.summary.json`
