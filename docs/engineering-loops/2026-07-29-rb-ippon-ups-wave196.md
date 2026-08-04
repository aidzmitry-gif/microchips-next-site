# RB catalogue wave 196 — IPPON UPS manufacturer-primary enrichment

Date: 2026-07-29  
Market: `microchips-by` (`ru-BY`)  
Scope: 24 existing Bitrix UPS cards; no new product identities were created.

## Result

- 24 existing IPPON UPS cards received an exact model identity, manufacturer-backed description and comparable attributes: topology, apparent power, active power and output waveform. `Innova G2 2000L` also has the exact manufacturer-stated zero transfer time.
- All 24 cards are assigned only to `catalog/power-systems/ups-systems`; 24 former preview paths were retired with preview-only 301 redirects.
- Every card remains `availability=on_request`, `price=null`, `is_indexable=false`, with no `Offer` schema. No commercial fact was inferred from the manufacturer catalogue.

## Primary evidence

Official IPPON catalogue:

`https://static.ippon.ru/data/download/Ippon_UPS_Catalogue_II_2024.pdf`

Covered series and exact variants:

| Series | Cards | Official catalogue evidence |
|---|---:|---|
| Back Basic | 4 | models 650/850/1500/2200, VA/W and modified sine wave |
| Back Basic S Euro | 2 | models 650/850 S Euro, VA/W and modified sine wave |
| Back Office | 3 | models 400/600/1000, standby topology, VA/W and modified sine wave |
| Back Verso | 1 | model 800, standby topology, 800 VA/420 W and modified sine wave |
| Back Power Pro II | 4 | models 500/600/700/800, VA/W and modified sine wave |
| Back Comfo Pro II | 3 | models 650/850/1050, VA/W and modified sine wave |
| Smart Power Pro II | 6 | models 1200/1600/2200 and Euro versions, VA/W and modified sine wave |
| Innova G2 L | 1 | model 2000L, online double-conversion topology, 2000 VA/1800 W, sine wave and 0 ms transfer time |

The canonical `mpn` field contains the exact manufacturer model designation visible in both the legacy card title and the official table. Numeric values labelled `Артикул` in the PDF were deliberately not promoted into identity: the same 2024 catalogue prints `74262` for both Back Office 400 and Back Office 1000, so treating that column as globally unique would create a false collision.

## New safety gate

Explicit `official_manufacturer_catalogue / manufacturer_primary` evidence now requires:

1. `identity_scope=exact`, `evidence_scope=exact_model`, HTTPS source, publisher and checked date.
2. Manufacturer boundaries plus an exact model suffix in the existing catalogue title and any replacement display name; `1050` cannot match `1050 Euro` or `1050 S Euro`.
3. A non-empty manufacturer technical-attribute map.
4. No repeated exact MPN inside the manifest and no existing canonical product with the same normalized MPN or SKU.
5. A pinned Bitrix staging lineage bound to the same site, Product, SiteProduct, namespace, external ID, materialization kind, staged row and site-scoped source run; both payload copies must state `transfer_status=legacy_only_draft_candidate`, so all `hold_*` records are blocked.
6. Matching applied provenance again at preview publication time, including normalized manufacturer and MPN equality across the applied evidence, Product and preview manifest.

Dealer-backed `model_core` behavior remains separate and unchanged; it still cannot create a canonical MPN.

## Verification evidence

- PHPUnit: `36 tests, 116 assertions` — PASS, including suffix, held-lineage, unrelated-lineage, applied-evidence, MPN/MPN and MPN/SKU collision cases.
- Laravel Pint: 6 changed PHP files — PASS.
- Final description dry-run import `893`: 24 rows (`0 created`, `24 refreshed`, `0 unchanged`).
- Final description apply import `894`: 24 rows (`0 created`, `24 refreshed`, `0 unchanged`).
- Content dry-run import `895` and apply import `896`: one new exact card (`Innova G2 2000L`) applied, 23 unchanged, 0 publication or commercial-field changes.
- Preview dry-run/apply: 24 products, 2 category nodes, 0 verified-price products, 0 indexable URLs, 0 offers.
- Wave verifier: 24/24 products, 24 distinct paths, 0 price-evidence rows, 0 duplicate MPN groups, PASS.
- RB SEO audit: 16,858 checked URLs, 46 redirects, 0 blocking issues, PASS.
- PostgreSQL post-check: 24 manufacturer IDs, 24 MPNs, 24 published previews, 24 and only 24 target-category memberships, 24 null prices and 24 `on_request` statuses; global duplicate normalized MPN groups: 0.
- Runtime API: 27 published IPPON cards in the UPS category including earlier waves; manufacturer, active-power and topology facets are present. `power=360 Вт` and `topology=Резервная (off-line)` each return 4 matching records.
- Runtime SSR samples (first/middle/last, including `Innova G2 2000L`): HTTP 200, self-canonical, `noindex`, no `Offer`, no numeric price and visible on-request wording.
- Corrected false-match paths for `25123/25131` return 404; restored legacy-preview paths return 200 and remain noindex.

## Held scope

The other 31 IPPON legacy cards remain outside this bounded wave for different reasons: some need a specific source or an explicit alias decision, some have an existing 1C identity link, and some are collision holds. They were not guessed into the verified set.

- `bitrix:25121`, `bitrix:25122` and `bitrix:25126` remain unpublished `hold_one_c_collision` records against 1C `КА-00003995`; no product URL or manufacturer-primary draft remains.
- `bitrix:25110`, `25115`, `25117`, `25118`, `25123` and `25131` fail the strict exact-name gate. The first two omit the official `S`, the next two add a legacy `New` suffix, and the last two use `650/850 Euro` where the official table says `Euro 650/850`.
- `bitrix:25123` and `bitrix:25131` were returned to their original published, noindex Bitrix-preview state: blank manufacturer/MPN, exact legacy description, legacy category/path and no temporary redirect.

## Readiness

This wave materially improves the verified UPS slice but does not move the whole project through the next 10% completion threshold. Confirmed overall readiness remains 60%; the full catalogue, media-rights verification, current commercial facts and production launch gates remain incomplete.
