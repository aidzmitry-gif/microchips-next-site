# RB catalogue filters and ranking wave — 2026-07-27

## Result

- Added SSR GET filters for manufacturer, technology, nominal voltage and capacity.
- Added API facets, applied-filter metadata, manufacturer and summary attributes to catalogue cards.
- Replaced misleading “relevance” behaviour with deterministic search ranking: exact SKU/MPN, exact name, name prefix, manufacturer, then substring.
- Removed price sorting while the RB catalogue has no confirmed local prices.
- Pagination preserves query, sort and filters; every query combination remains `noindex,follow`.
- Electronic components were not touched.

## Verification

- Backend catalogue API tests: 8 tests / 45 assertions PASS.
- Backend controller subset: 5 tests / 27 assertions PASS.
- Frontend Vitest: 16 files / 77 tests PASS.
- TypeScript `--noEmit`: PASS.
- ESLint: 0 errors.
- Next.js 16.2.10 production build: PASS.
- Live API category check: 30 products, 8 manufacturer options, 2 technologies, 3 voltage options and 12 capacity options.
- Live combined filter `Ventura + AGM`: 6 products with correct applied-filter metadata.
- In-app browser desktop and 390×844 mobile checks: no horizontal overflow; filter grid collapses to one column on mobile.
- Browser form interaction: selecting voltage submits a stable GET URL and renders the honest empty state for an unavailable combination.
- Browser console: 0 errors.

## Known next step

Current facets are computed from the published category/search set and use normalized source-backed JSON values. Before thousands of published cards, move the same contract onto typed `product_filter_values` so numeric ranges and contextual facet counts remain efficient and unambiguous.
