# RB catalogue — family correction and verified GP12170 pilot (Wave 135)

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`  
Fixed catalogue denominator: 7,286 products

## Outcome

- Corrected the false GP1272 family before indexation.
- Kept one visible `CSB GP1272 F2` card (`КА-00001364`) with its existing
  verified owned image and one canonical noindex URL.
- Removed execution-specific 12V25W facts that did not belong to the base
  GP1272 identity. The surviving facts are 12 V, 7.2 Ah, VRLA-AGM,
  F2/Faston 250, 150.9 × 64.8 × 98.6 mm and approximately 2.40 kg.
- Excluded the remaining exact GP12170 B3 country duplicate
  `ФР-00001475 → КА-00000471` from the RB site profile. Canonical shared
  products and other markets were not deleted.
- Created the first true regional family: one noindex GP12170 B1 canonical
  page (`КА-00001066`) with a URL-less selectable B3 option
  (`КА-00000471`). B1 and B3 are materially different M5 terminal positions.
- Corrected the B3 category from rechargeable cells to the canonical
  `Аккумуляторы для ИБП` category through family synchronisation.

## Safety improvements

- Families are scoped by `site_id`; an RB grouping cannot hide an independent
  RU/UZ catalogue card.
- The importer verifies manufacturer, model core, shared facts and option facts
  for every child against an applied source record.
- A manifest cannot silently remove an active option and leave a published
  URL-less orphan.
- Variant path retirement accepts only normalized safe local paths and never
  retires an indexable path automatically.
- Family and duplicate changes explicitly revalidate the canonical URL,
  `/catalog` and `/sitemap.xml`.
- A reviewed description manifest can explicitly remove named stale legacy
  attributes. Removal is recorded in the applied draft and cannot silently
  remove an unlisted field.
- Selecting an option keeps URL/H1/canonical identity unchanged, switches its
  verified facts, commercial state, media when present and sends a typed quote
  cart line. The canonical selection also sends its own product identity.

## Source evidence

- Current CSB GP series page:
  <https://csb-battery.com/product/gp-series/>
- Current GP12170 datasheet:
  <https://csb-battery.com/wp-content/uploads/2026/03/CSB-Datasheet-GP12170-01312026.pdf>
- Current CSB catalogue with base GP1272 and terminal/weight distinctions:
  <https://csb-battery.com/wp-content/uploads/2026/03/CSB-Catalog-2026-Digital-Spread-1.pdf>

The GP12170 datasheet lists B1/B1B/B3 as M5 terminal options. Capacity is not
flattened into one precise family fact: the current individual datasheet reports
values by discharge regime, while the catalogue rounds the nominal model class.

## Applied evidence

- False-family collapse: dry-run `collapsed=1`; apply deleted one RB
  `SiteProduct`, zero shared products; repeat dry-run `already_collapsed=1`.
- B3 duplicate exclusion: dry-run and apply passed for one unpublished RB row.
- Source refresh: GP1272 `1/1` and GP12170 `2/2` applied; no publication or
  commercial field was changed by the content command.
- GP12170 family: dry-run, apply and immediate idempotent re-apply passed;
  `families=1`, `variants=1`, `variant_urls_created=0`,
  `indexable_resources_created=0`.
- Database: one verified RB family; B3 child URL count `0`, SEO record count
  `0`; false GP1272 family count `0`.
- Flat API searches: `GP1272 total=1`, `GP12170 total=1`.
- Catalogue API: 232 visible canonical cards; database contains 233 published
  site products because one URL-less B3 option is selected inside its family.
- SEO audit: PASS, 261 checked URLs, 0 blockers.
- Frontend focused test: 4/4 passed; TypeScript and Next.js production build
  passed.
- Backend family/content suite: 8 tests, 69 assertions passed; the final
  removal-only regression also passed in 3 tests, 25 assertions.
- Browser interaction: B3 became checked and exposed only `B3 / M5`; URL and
  H1 remained the B1 canonical page.

## Progress accounting

Strict content-complete coverage remains **77 / 7,286 = 1.06%**. This wave
improves correctness and creates a reusable multiplier, but GP12170 has no
verified storefront image and therefore receives no strict-complete credit.
Visible canonical catalogue coverage remains **232 / 7,286 = 3.18%**.

## Next production cycle

Use the old Bitrix catalogue as a noindex staging baseline, intersect it with
the allowed 1C assortment, and process hundreds of rows per wave:

1. preserve useful legacy URL/content/media evidence;
2. exclude electronics and 1C-absent products;
3. collapse exact duplicates before enrichment;
4. group only explicit, source-proven material variants;
5. correct stale attributes with reviewed removals;
6. publish noindex previews in bulk; keep image rights/visual verification as
   the separate strict-completeness gate.
