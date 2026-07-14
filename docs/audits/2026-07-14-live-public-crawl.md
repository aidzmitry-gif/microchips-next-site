# Read-only public SEO snapshot: microchips.by

Audit time: 2026-07-14T07:38:01+03:00. Scope: public unauthenticated observation only. No production requests that change state, logins, forms, carts, or admin tools were used.

This is a small evidence sample for the migration registry, not a substitute for a complete crawler export. The prior [Bitrix source audit](2026-07-14-bitrix-source-audit.md) remains the authoritative snapshot of the 2026-06-23 backup.

## Method and confidence

1. Read the public homepage and one public category with a read-only HTML extractor.
2. Queried the public search index for representative commercial, product, technical and contact URLs. Search-index crawl dates are recorded below because they limit freshness.
3. Used the repeatable read-only command `./scripts/capture-public-seo-snapshot.ps1` after a direct HTTPS connection became available. It stores raw headers and bodies only in ignored local audit output; it does not authenticate, submit forms, retain cookies or change production data.

The capture at `2026-07-14T07:43:36+03:00` retrieved all 15 selected URLs: 15 HTTP `200` responses, zero redirect hops, 10 self-canonical HTML pages and 9 pages with both title and H1. Search results remain supporting evidence for prior indexability; the direct capture is the evidence for current status, final URL, title, H1 and canonical in this limited priority sample.

## Publicly observed sample

| URL | Evidence and freshness | Visible title / H1 evidence | Registry disposition | Confidence |
| --- | --- | --- | --- | --- |
| `https://microchips.by/` | Homepage HTML read during this audit; search index crawled last month. | Title: `Microchips - каталог батареек и аккумуляторов. Оптовые цены, доставка по Минску и Беларуси`. | `keep` as the country-site homepage. Rebuild rather than copy the legacy markup. | High for existence and local commercial content; no canonical/header proof. |
| `https://microchips.by/catalog/` | Search index crawled 3 weeks ago. | Title: `Каталог товаров Microchips`; H1: `Каталог товаров`. | `keep`; priority core catalogue route. | Medium. |
| `https://microchips.by/catalog/akkumulyatory/` | Search index crawled last month; it showed 13,671 products. | Title: `Аккумуляторы купить в Минске по низким ценам`; H1: `Аккумуляторы`. | `keep`; priority top-level commercial route. | Medium. |
| `https://microchips.by/catalog/akkumulyatory/promyshlennye/` | Search index crawled 6 months ago; it showed 1,904 products. | Title: `Промышленные аккумуляторы купить в Минске`; H1: `Промышленные аккумуляторы`. | `keep`; priority B2B landing route. Revalidate live metadata before launch because the evidence is stale. | Medium for route; low for current count/metadata. |
| `https://microchips.by/catalog/akkumulyatory/dlya_ibp/` | Search index crawled last month; it showed 1,097 products. | Title: `Купить аккумулятор для ИБП (бесперебойника) в Минске`; H1: `Аккумуляторы для ИБП (бесперебойника)`. | `keep`; priority B2B landing route. | Medium. |
| `https://microchips.by/catalog/akkumulyatory/dlya_ibp/1543/` | Search index crawled 3 months ago. | Title/H1 evidence: `Аккумулятор для ИБП 18Ач Minamoto MB12180`; visible price and technical attributes. | `keep_candidate`; preserve legacy numeric ID `1543` as a migration identity, then map only to the approved new product. | Medium for historical public indexability; no current availability or canonical proof. |
| `https://microchips.by/catalog/mikroelektronika/aktivnye_elementy/mikroskhemy/` | Category HTML read during this audit; search index crawled last month and showed 84 items. | Title: `Микросхемы купить в Минске`; H1: `Микросхемы`. | `keep`; priority technical category. | High for route/content accessibility; no canonical/header proof. |
| `https://microchips.by/contacts/` | Search index crawled last month. | Title: `Наши контакты`; H1: `Контакты`. It exposes Minsk address, phone, email and working hours. | `keep_or_fix`; retain a real Belarus contact page, but revalidate legal data before publishing. | Medium. |

The homepage and public snippets consistently expose Belarus commercial facts: `ООО "АККУМУЛЯТОРНЫЕ РЕШЕНИЯ"`, UНП `192766048`, Minsk address, +375 phone, and business hours. These are evidence for the RB site only; they must not be copied to Russian, Uzbek or fourth-market pages.

## Comparison with the Bitrix source snapshot

The public navigation and the source snapshot agree on the core catalogue tree: batteries, rechargeable batteries, accumulators, power supplies, chargers, microelectronics, flashlights and warehouse equipment. Public pages still use the source's slash-terminated hierarchy and numeric product endpoint pattern:

```text
/catalog/<section path>/<numeric product ID>/
```

Four public root-category counts match the source-audit snapshot exactly: batteries (1,630), power supplies (687), chargers (284) and microelectronics (295). The public catalogue result displayed 13,665 accumulators, while the source audit counted 13,165 products with that root as their primary section; it also displayed 2,216 rechargeable batteries, versus 1,080 in that source grouping. These figures use different observation methods and must not be treated as product additions/deletions until the inventory is reconciled by source ID, SKU/MPN and primary section.

Search results also show indexable SEO/filter-style routes such as brand (`/dlya_ibp/apc/`) and attribute (`/promyshlennye/dlya-telekommunikatsiy/48-v/`) paths. This is consistent with the source audit's 5,089 Aspro sitemap landing candidates. They are `seo_landing_candidate`, not automatic `keep` decisions.

## Direct technical checks

| Check | Result | Registry consequence |
| --- | --- | --- |
| HTTPS reachability of homepage | `200`, no redirect, self-canonical. | Keep as the RB homepage candidate; rebuild content rather than copy markup. |
| `robots.txt` | `200`; live policy still disallows service/search/sort and `/filter/*/apply/` routes and points to the root sitemap. | Carry only the intent into the new rules; do not copy the Bitrix file verbatim. |
| Sitemap | Root index and all three referenced maps returned `200` without redirects. Live counts are 17,707 `<loc>` in `sitemap-iblock-26.xml` and 5,089 in `aspro-sitemap/sitemap-1.xml`. | The source inventory matches the live catalogue and landing-map counts at capture time. |
| HTTP status and redirect chain | All 15 priority sample URLs returned `200` with zero observed hops. | Final migration must still test every approved redirect row, not extrapolate from the sample. |
| Canonical and robots meta | Ten HTML pages had self-canonicals on `microchips.by`; no selected page exposed a robots meta tag. | The new site must preserve self-canonical behaviour deliberately; no cross-country canonical is approved from source data. |
| Title and H1 | Nine content pages exposed both direct-response title and H1. The homepage had a title but no first `<h1>` in the raw response. | Use them as regression baselines; the new homepage needs an intentional, accessible H1. |

## Registry-ready decisions and blockers

1. Seed `keep` rows for the homepage, `/catalog/`, the accumulator root, industrial accumulators, UPS accumulators, microchips and contacts. They are high-value, publicly visible routes that must receive a self-canonical equivalent on `microchips.by`.
2. Keep legacy numeric product IDs as immutable source identities. A product URL such as `/1543/` receives a final `keep` or exact `redirect` only after product identity and publication status are approved; never redirect a missing product to the homepage.
3. Keep RB legal/contact facts site-scoped. They are live public evidence for Belarus but do not transfer to other country profiles.
4. Queue brand, voltage and other parameter routes as `seo_landing_candidate`. They require demand, distinct commercial content, approved filters and one canonical URL before indexation.
5. Award the data/SEO validation criterion only for the stated priority patterns: the repeatable snapshot captured live sitemap, robots, HTTP status, redirect count, title, H1 and canonical evidence. It does **not** approve all 22,796 source URLs or any final redirect destination.

## Required next measurement

Before an RB migration release, expand the same read-only capture to every approved priority URL. The report must include final URL, status, redirect hops, `X-Robots-Tag`, robots meta, canonical, title, H1, hreflang, response size and sitemap source, then compare it with the 22,796-row source inventory.
