# RB catalogue sorting gate — 2026-07-27

## Delivered contract

The catalogue API accepts only four explicit sort values:

- `name_asc`, `name_desc`;
- `price_asc`, `price_desc`.

The default keeps the editorial site-product order. Price sorts keep products
without a confirmed local price after products with actual offers. Arbitrary
column names are rejected by request validation (`422`), so a query parameter
cannot become a database expression.

The customer-facing catalogue form exposes the same allow-list. Sorting and
search query URLs remain non-indexable in the Next.js metadata policy, while
the category's self-canonical URL stays unchanged. This prevents filter/sort
URL proliferation from becoming SEO duplicates.

## Verification

- PHP syntax: `CatalogController` and its feature test pass `php -l`.
- Frontend lint: 0 errors (one pre-existing unused-component warning).
- Frontend Vitest: **16 files, 76 tests passed**.
- Production frontend build: passed during local Docker image rebuild.
- Local HTTP: allowed `sort=name_asc` returns `200`; untrusted sort value
  returns `422`.

## Deliberate limitation

There are no voltage, capacity, chemistry or dimension filters yet. The
current 1C import does not contain enough primary-source-confirmed attributes
to make such filters truthful. They will be introduced per category only after
the relevant attributes and their provenance are complete.
