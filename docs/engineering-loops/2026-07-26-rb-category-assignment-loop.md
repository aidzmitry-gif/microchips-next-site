# RB: verified taxonomy and category assignment loop

Date: 2026-07-26.

## Source boundary

The category tree is derived only from the read-only Bitrix section snapshot. The existing non-public RB tree contained `Аккумуляторы → Для ИБП → AGM` (external IDs `372 → 409 → 410`). The snapshot independently contains the sibling `GEL` section (`411`), so only that verified node was added.

No category was created from a product title, manufacturer name, AI inference, or SEO keyword.

## Applied operations

| Import run | Operation | Result |
| ---: | --- | --- |
| 28 | Taxonomy delta dry-run | 1 valid GEL category, no write |
| 29 | Taxonomy delta apply | 1 non-public GEL category created |
| 30 | Product assignment dry-run | 27 valid assignments and 27 explicit chemistry values, no write |
| 31 | Product assignment apply | 27 category links and provenance-tagged chemistry facts written |

The 27 assignment rows come directly from the three evidence decision files. `AGM` records link to Bitrix section `410`; `GEL` records link to section `411`. The assignment command neither changes nor reads `is_published`.

## Verified result

| Check | Result |
| --- | ---: |
| RB product drafts | 50 |
| RB category-product links | 50 |
| Product drafts with a category link | 50 / 50 |
| Newly added GEL section | 1 |
| Public RB product cards | 0 |

The chemistry facts live on the shared `products` model because chemistry is technical, not market-specific. Their provenance explicitly states `operator_supplied_csv_column`; that provenance is not emitted in public API attributes.

## Readiness impact

The RB criterion **catalog and lead-flow validation** is now complete: the bounded 50-product catalog is identity-checked, duplicate-guarded, linked to a source-derived category tree, and has a local-inbox lifecycle. This increases RB readiness from 40% to 60% and the weighted platform total from **51.0% to 54.0%**.

This does not satisfy SEO/GEO release or make the product URLs public. Those require localized indexable pages, staging DNS/TLS and an external crawl/release audit.
