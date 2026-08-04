# RU safe catalog preparation loop — 2026-07-26

## Scope

Prepare a technical, non-public Russian catalog slice from already confirmed
shared Product identities. This is explicitly not a Russia launch and must
not be confused with owner-confirmed Russian commercial data.

## Guarded draft clone

`catalog:clone-site-draft-slice microchips-by microchips-ru --expected-count=50`
validated the exact source size before an apply. The apply created only
target `SiteProduct` drafts. A repeat was idempotent.

The clone copies only `product_id`. It does not read or copy source-market
slug, availability, price, SEO, category, URL, contact, commercial fact or
publication state. The new target records are `is_published=false`,
`availability=on_request`, without price or SEO.

## Taxonomy and assignments

The non-public technical tree contains 4 categories: `Аккумуляторы → Для ИБП
→ AGM/GEL`. Import runs 34–39 completed dry-run/apply for the tree and the
two pre-existing evidence assignment packages.

Post-import aggregate verification:

- 50 RU site products;
- 0 published RU products;
- 50 products with a category assignment;
- 4 RU categories; 0 published RU categories;
- 0 RU contacts and 0 RU commercial facts were created by this loop.

## Local inbox proof

A deliberately marked QA-only request to `microchips-ru.test` was accepted
by the local inbox and closed by operator id 1 with a note stating that no
customer contact was used. Bitrix24 was not invoked.

## SEO safety

`seo:audit microchips-ru --json` passed with zero sitemap URLs and zero
blockers. `site:launch-preflight microchips-ru --json` correctly remains
blocked by `INDEXABLE_URL_MISSING`; that is expected before real RU content
and a country launch decision.

## No readiness-score inflation

This loop can support the future "catalog and local inbox" criterion for
Russia, but does not supply the real RU domain, legal entity, contacts,
delivery/payment/warranty rules, or country SEO content. Those facts are
required before any Russia readiness score is claimed.
