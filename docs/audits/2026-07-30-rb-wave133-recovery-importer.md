# Wave133 guarded recovery importer

The recovery command accepts only `microchips-by` and the immutable 558-row snapshot whose SHA-256 is
`19cadbd298f6326e8675e0b834730af7f198a203e05ec55027f554eabf408985`. Any site mismatch, hash drift,
row-count/topology drift, duplicate snapshot key, missing category, or existing-record conflict aborts the
transaction.

For a missing record it preserves the snapshot product external ID, SKU, MPN, manufacturer, product slug,
name, short description, technical attributes and status; it also preserves the site-product slug and exact
category external ID. New site products are always unpublished, have a null price and SEO, and receive no URL.
Existing products and site products are never updated. A missing category link may be attached only while the
site product is unpublished; changing the category of a published card is refused.

The command defaults to a rolled-back dry-run. `--apply` exists only for an explicitly authorised recovery.
No live apply was performed during this work.

## Verification

The full snapshot passed an isolated SQLite `:memory:` test: dry-run rollback, creation of 558 products, 558
unpublished site products and 558 category links, complete field-by-field content comparison, zero URLs/prices/
SEO/publication, an idempotent second run, and fail-closed product-conflict, wrong-site and hash-drift cases.
PHPUnit result: **2 tests, 6164 assertions, exit 0**.
