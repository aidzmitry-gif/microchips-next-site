# Product media verification gate — 2026-07-27

## Why this gate exists

A search result or retailer image is not evidence that a photograph depicts
the exact SKU, and it does not grant a right to reuse it. Product media is
therefore modeled separately from product text and starts unpublished.

## Required evidence before a storefront image can be shown

1. `source_page_url`: the official manufacturer page or other recorded source;
2. `source_asset_url`: the exact original asset, when available;
3. `rights_basis`: why storing and displaying the asset is permitted;
4. local `storage_path` and `content_sha256`: a durable, deduplicated file;
5. `verification_status = verified`, verification note and timestamp: the
   exact MPN/model, terminals, form factor and branding have been visually
   checked against the selected product;
6. explicit `is_published = true`.

The `storefrontReady` query scope requires every one of these conditions. A
pending, rejected, remote-only or rights-unknown image cannot enter the public
product payload merely because its URL exists.

## Applied database evidence

- Migration `2026_07_27_000001_create_product_media_table` passed `--pretend`.
- It was then applied to local PostgreSQL.
- Table `public.product_media` and the public-lookup index exist.
- No media records, files, products or publication flags were created by the
  migration.

## Next execution phase

Start with exact primary-source model pages already verified for editorial
drafts. For every candidate image, retain the source page, check visual model
match, record rights basis, store the hash, and only then create a public media
record. Retailer images remain excluded by default.
