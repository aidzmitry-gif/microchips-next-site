# RB B2B catalogue loop — waves 174–193

Date: 2026-07-29. Site: `microchips-by`.

## Result

- Prioritized 3,936 existing B2B cards and selected a no-repeat queue of 500.
- Researched 255 terminal/scanner battery records against official OEM
  documentation; applied 11 exact or bounded source-backed descriptions.
- Collapsed one confirmed Honeywell BAT-EDA50K-1 duplicate while preserving
  the retired legacy URL with a 301 redirect.
- Added 68 genuinely new CSB B2B models absent from Bitrix and 1C: eight XTV,
  ten XHRL, four XHRL-FT, eleven EVX, four EVH, nine MSJ and 22 models from
  XPL, XPL-FT, HR, HRL and UPS.
- Added 26 absent official EnerSys identities: seventeen DataSafe HX and nine
  PowerSafe V-FT models.
- Added 24 absent current CSB industrial identities from the GPL, TPL, MSV,
  MU and RE series after exact-MPN and hidden brand/model duplicate checks.
- Added 12 absent EnerSys PowerSafe GFM industrial modules with exact
  model-level voltage, C10 capacity, dimensions and mass from the official
  range table.
- Added 14 absent EnerSys PowerSafe OPzV industrial cells with exact
  model-level C10 capacity, dimensions and mass from the official range table.
- Added 32 absent EnerSys PowerSafe SBS TPPL batteries: 21 top-terminal and
  11 front-terminal models, with exact model-level voltage, C10 capacity,
  dimensions and mass from the official manufacturer range tables.
- Added 25 absent EnerSys PowerSafe VGM industrial Ni-Cd cells with exact
  model-level five-hour capacity, dimensions and typical mass from the current
  official range table. A conflicting voltage value on a separate official
  webpage was deliberately not propagated into the cards.
- Added the nine remaining safe exact identities found in the current CSB
  catalogue: four Calor XHT-FT, three XTV-WT, one RE 48V and one PowerBox
  system. Ambiguous catalogue dimensions were omitted instead of copied.
- Added 25 absent EnerSys PowerSafe VGL industrial Ni-Cd cells with exact
  model-level five-hour capacity, dimensions and typical mass from the 2024
  official range table. The same cross-source voltage conflict was held back.
- Added 23 absent EnerSys PowerSafe RL industrial Ni-Cd cells after excluding
  two ambiguous RL/HRL near-matches. The range table remains linked from the
  current manufacturer page; nominal voltage was withheld because first-party
  surfaces conflict.
- Added 20 absent LEOCH identities from manufacturer PDFs revised January
  2026: fifteen flooded OPzS industrial cells and five LP VRLA-AGM reserve
  batteries, each with exact voltage, rated capacity, dimensions and mass.
- Added the complete 21-model Exide Classic OPzS Solar 2 V wet-cell table from
  the current manufacturer datasheet. Long exact part numbers remain MPNs,
  while readable OPzS type labels are used in product names.
- Added 16 absent LEOCH LPF front-terminal VRLA-AGM models from the current
  manufacturer catalogue, preserving parenthesized and suffix variants as
  distinct exact identities.
- Added the complete 44-model EnerSys PowerSafe RM Ni-Cd table after exact
  identity checks replaced a lossy substring hold. Exact C5 capacity,
  dimensions and unpacked mass are retained; nominal voltage is withheld due
  to a direct conflict between two official EnerSys sources.
- Added 19 absent LEOCH LPL II 2 V VRLA-AGM stationary cells from the current
  manufacturer catalogue. Waves 189–192 therefore form an exact 100-card
  source-backed batch.
- Added the complete 29-model EnerSys PowerSafe RH high-current Ni-Cd table.
  Exact C5 capacity, dimensions and unpacked mass are retained; voltage remains
  withheld because current official EnerSys sources disagree.

## New manufacturer-backed cards

All 407 new manufacturer-backed cards:

- return HTTP 200;
- expose manufacturer and exact MPN identities; category and technology facets
  follow the source-backed series rather than a universal UPS/AGM assumption;
- emit voltage facets only when the relevant source establishes them;
- remain `noindex`;
- use `on_request` and have a null numeric price;
- emit no price evidence and no invented commercial offer.

The EnerSys RM and RH model tables are still linked from current manufacturer
pages but are dated January 2014. Their model-level facts therefore remain
preview evidence and require source revalidation before an indexable release.

Published RB market-row count changed from 16,415 to 16,821: one exact
duplicate market row was removed and 407 net-new B2B models were added. One
published row is an active member of a verified product family and therefore
does not consume a second catalogue card; the storefront/API exposes 16,820
canonical cards. The broad distinct published B2B slice changed from 3,936 to
4,342 (4,341 canonical visible cards). The reviewed groups now contain 1,233
published UPS-battery rows, 174 traction-battery cards and 1,143
industrial-battery cards before wave 193. The final verified count after wave
193 is 1,172.

## Reusable engineering change

`catalog:import-manufacturer-product-candidates` now provides a dry-run-first,
transactional boundary for net-new official-manufacturer products. It creates
only unpublished drafts, rejects normalized SKU/MPN collisions and does not
create URLs, SEO state, prices, availability claims beyond `on_request`, or
publication. Existing source-backed description and preview commands remain
the independent gates for content and storefront visibility.

The series-manifest builder supports exact per-model facts layered over shared
series facts and can now keep an exact manufacturer MPN separate from a
readable product type label. Catalogue facet extraction recognizes explicit
C5, C10 and C120 capacity and carries a schema version in its Redis key, so a
deployment cannot reuse records generated by older extraction semantics.

## Commercial truth snapshot

The current RB database has 57 current price-evidence rows, all sourced from
the legacy site. Thirty-four published cards expose a numeric price. No
published card claims `in_stock`, because no synchronized stock feed exists.
The new manufacturer-backed cards therefore remain `on_request` with a null
price and no `Offer`; adding a display price or stock flag solely for search
appearance remains prohibited.

Preview slug corrections are stored with redirect purpose `preview`. Release
SEO redirects retain purpose `seo` and still require an indexable published
target; preview redirects require a published target but may point to the
deliberately noindex replacement preview. The migration backfilled the seven
existing noindex-target redirects. This removed a false conflict without
weakening the launch rule for real legacy SEO redirects.

## Verification

- PHP syntax checks passed for the new command and feature test.
- Candidate dry-runs: 8 XTV plus 14 XHRL/XHRL-FT plus 24 EVX/EVH/MSJ plus
  22 XPL/XPL-FT/HR/HRL/UPS plus 26 EnerSys createable, 0 unchanged, 0
  duplicate collisions.
- Candidate applies: 407 created initially as unpublished drafts.
- Description stage/apply and preview dry-run/apply: all 407 accepted.
- Database: 407/407 published as `on_request`, price null, no indexable URLs.
- Duplicate control: zero repeated normalized MPN groups in either new model
  set.
- Storefront samples XTV1272 and XTV121100: HTTP 200, visible name and
  `noindex`.
- Catalog API query `q=XTV`: exactly 8 results with eight distinct paths;
  `q=XHRL`: exactly 14 with 14 distinct paths.
- Catalog API queries: `q=EVX` = 11, `q=EVH` = 4 and `q=MSJ` = 9, each
  with one distinct path per result. All 24 expose CSB and AGM; EVX/EVH expose
  12 V and MSJ exposes 2 V.
- Runtime resolver samples EVX1272 and MSJ-1000 return product payloads with
  the expected canonical paths, `on_request`, null price and
  `isIndexable=false`.
- Full products table: zero duplicate non-null normalized MPN groups; the 24
  wave-177 records also have zero duplicate normalized names.
- Wave 178 database boundary: 22/22 published, 22 noindex URLs, zero prices;
  the B2B total is 4,003 and `Аккумуляторы для ИБП` contains 1,166 cards.
- Runtime resolver sample HRL1250W returns the exact CSB MPN under the UPS
  battery path with `on_request`, null price, `isIndexable=false` and no Offer
  schema.
- Wave 179 database boundary: 26/26 EnerSys cards published, 26 noindex URLs,
  zero prices; full RB = 16,508, B2B = 4,029 and UPS batteries = 1,192.
- MPN `+` is now preserved as `-plus` in generated slugs. Six already-created
  DataSafe HX Plus paths were replaced by distinct canonical noindex paths;
  each old path is retired and resolves to an active HTTP-301 decision.
- Runtime redirect check: the former `enersys-12hx650f-fr` path resolves to
  `enersys-12hx650f-fr-plus`; the target resolves as product MPN
  `12HX650F-FR+` and remains noindex.
- Wave 180 database boundary: 24/24 CSB GPL/TPL/MSV/MU/RE cards published,
  24 distinct MPNs and 24 distinct product paths, zero prices and zero
  indexable URLs; full RB = 16,532, B2B = 4,053 and industrial batteries =
  925.
- API exact-identity checks for GPL12800G, TPL121000TFR, MSV-1000, MU-1000
  and RE1700 each return exactly one product with the expected path,
  `on_request` and null price. The RE1700 storefront route returns HTTP 200,
  contains the exact model and `noindex`, and emits no `Offer` schema.
- The full products table still contains zero repeated non-null normalized MPN
  groups after wave 180.
- Wave 181 database boundary: 12/12 EnerSys PowerSafe GFM cards published,
  12 distinct MPNs and product paths, zero prices and zero indexable URLs;
  full RB = 16,544, B2B = 4,065 and industrial batteries = 937.
- The series generator now supports separately validated per-model facts over
  shared series facts. Its two focused Python tests pass.
- Runtime samples 6GFM200 and 3GFM2000 preserve their exact model-level
  voltage, C10 capacity, dimensions and mass. The catalogue now recognizes
  `Номинальная ёмкость C10` as the capacity facet; an exact 200 А·ч filter
  returns 6GFM200. A facet schema version prevents deployment from reusing
  Redis records generated by older extraction semantics.
- Wave 182 database boundary: 14/14 EnerSys PowerSafe OPzV cards published,
  14 distinct MPNs and product paths, zero prices and zero indexable URLs;
  full RB = 16,558, B2B = 4,079 and industrial batteries = 951.
- Exact API and storefront checks for 4 OPzV 200 return GEL, 2 В and 215 А·ч;
  the combined technology/voltage/capacity filter returns exactly that card.
  Its route returns HTTP 200 with `noindex` and no `Offer` schema.
- Post-migration `seo:audit microchips-by --json`: PASS across 16,595 routes
  and seven redirects, with zero blockers. There are deliberately zero sitemap
  URLs because the catalogue remains a noindex preview; URL promotion remains
  a separate release gate.
- XTV filters: manufacturer CSB = 8, normalized technology AGM = 8, voltage
  12 V = 8. XHRL filters: manufacturer CSB = 14 and AGM = 14; the 12 V filter
  deliberately returns only the four XHRL-FT models whose series source
  explicitly states 12 V.
- Honeywell duplicate route returns HTTP 301 when tested with the configured
  `microchips-by.test` market host; the survivor returns HTTP 200.
- PHPUnit could not execute on the Windows host because its PHP runtime lacks
  `mbstring`; the production image intentionally excludes dev dependencies.
  No unsupported green PHPUnit claim is made.
- Wave 183 reusable verifier: 32/32 EnerSys SBS records found, 32 distinct
  canonical paths, zero price-evidence rows, zero duplicate normalized MPN
  groups and zero errors.
- Runtime query `q=SBS 210F` returns exactly one card with 12 V and 211 Ah.
  The combined EnerSys + AGM + 2 V + 310 Ah filter returns exactly SBS 300.
  The SBS 210F storefront route returns HTTP 200, `noindex`, null price and no
  `Offer` schema.
- Current `seo:audit microchips-by --json`: PASS across 16,627 routes and
  seven redirects, with zero blockers. The sitemap remains intentionally
  empty while the transferred catalogue is still a noindex preview.
- Wave 184 reusable verifier: 25/25 EnerSys PowerSafe VGM records found, 25
  distinct paths, zero price-evidence rows, zero duplicate normalized MPN
  groups and zero errors.
- API `q=VGM`: exactly 25 results and 25 distinct paths. The combined
  industrial-battery + EnerSys + documented Ni-Cd technology + 400 Ah filter
  returns exactly VGM 400. Its storefront route returns HTTP 200, displays the
  exact capacity, remains `noindex` and emits no `Offer` schema.
- Post-wave-184 `seo:audit microchips-by --json`: PASS across 16,652 routes,
  seven redirects and zero blockers.
- Wave 185 verifier: 9/9 CSB records, nine distinct paths, zero price evidence,
  zero normalized-MPN duplicates and zero errors. API returns exactly four
  XHT models; the CSB + AGM + 20 Ah industrial filter returns exactly
  XTV12200FR-WT. PB-300 resolves under `/catalog/power-systems`, and its page
  returns HTTP 200 with 72 kWh, `noindex` and no `Offer` schema.
- Wave 186 verifier: 25/25 EnerSys VGL records, 25 paths, zero price evidence,
  zero normalized-MPN duplicates and zero errors. API `q=VGL` returns exactly
  25 cards; the EnerSys + documented Ni-Cd technology + 420 Ah filter returns
  exactly VGL 420. Its page returns HTTP 200, `noindex` and no `Offer` schema.
- Current `seo:audit microchips-by --json`: PASS across 16,686 routes, seven
  redirects and zero blockers.
- Wave 187 verifier: 23/23 EnerSys RL products, 23 paths, zero prices/evidence,
  zero duplicate normalized MPN groups and zero errors. API query
  `q=PowerSafe RL` returns exactly those 23 canonical cards.
- Wave 188 verifier: 20/20 LEOCH products, 20 paths, zero prices/evidence,
  zero duplicate normalized MPN groups and zero errors. The 3000 Ah industrial
  filter returns exactly `24OPzS3000`; the AGM + 4.5 Ah UPS-battery filter
  returns exactly `LP4-4.5`. The OPzS storefront sample returns HTTP 200,
  `noindex` and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,729 routes, seven
  redirects and zero blockers.
- Wave 189 verifier: 21/21 Exide Classic OPzS Solar products, 21 distinct
  paths, zero price evidence, zero normalized-MPN duplicates and zero errors.
  API `q=OPzS Solar` returns exactly those 21 Exide cards. The industrial +
  Exide + 4600 Ah filter returns only `NVSL024600WC0FA`; its storefront page
  returns HTTP 200 with `noindex`, null price and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,750 routes, seven
  redirects and zero blockers.
- Wave 190 verifier: 16/16 LEOCH LPF records, 16 distinct paths, zero price
  evidence, zero normalized-MPN duplicates and no errors. API `q=LPF12`
  returns exactly 16 cards; the LEOCH + AGM + 200 Ah filtered query returns
  only `LPF12-200`. Its storefront page returns HTTP 200 with `noindex`, null
  price and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,766 routes, seven
  redirects and zero blockers.
- Wave 191 verifier: 44/44 PowerSafe RM records, 44 distinct paths, zero price
  evidence, zero normalized-MPN duplicates and no errors. API query
  `q=PowerSafe RM` returns exactly 44 cards with no voltage facet leakage; the
  EnerSys + 400 Ah filtered query returns only `RM 400`. Its storefront page
  returns HTTP 200 with `noindex`, null price and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,810 routes, seven
  redirects and zero blockers.
- Wave 192 verifier: 19/19 LEOCH LPL II 2 V records, 19 distinct paths, zero
  price evidence, zero normalized-MPN duplicates and no errors. API `q=LPL2`
  returns exactly 19 cards; the LEOCH + AGM + 3000 Ah filtered query returns
  only `LPL2-3000M`. Its storefront page returns HTTP 200 with `noindex`, null
  price and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,829 routes, seven
  redirects and zero blockers.
- Wave 193 verifier: 29/29 PowerSafe RH records, 29 distinct paths, zero price
  evidence, zero normalized-MPN duplicates and no errors. API query
  `q=PowerSafe RH` returns exactly 29 cards with no voltage facet leakage; the
  EnerSys + 800 Ah filtered query returns only `RH 800`. Its storefront page
  returns HTTP 200 with `noindex`, null price and no `Offer` schema.
- Final `seo:audit microchips-by --json`: PASS across 16,858 routes, seven
  redirects and zero blockers.
