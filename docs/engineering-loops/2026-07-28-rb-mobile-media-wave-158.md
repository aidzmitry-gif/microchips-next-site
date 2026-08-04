# RB mobile replacement-battery media transfer — wave 158

Date: 2026-07-28. Site: `microchips-by`.

## Scope and result

The complete mobile-device replacement-battery source slice was extracted in
one archive pass so later 10% cycles do not rescan the 4.4 GB Bitrix upload
archive. Only the bounded quantity required for the current milestone was
attached to catalogue products.

| Metric | Result |
| --- | ---: |
| Mobile staging rows | 5,506 |
| Safe legacy draft candidates | 5,303 |
| Exact same-element media references | 5,301 |
| Safe rows with no source image | 2 |
| Extracted raster assets | 5,301 |
| Rejected/corrupt assets | 0 |
| Prepared local asset bytes | 313,545,641 |
| Images attached in this wave | 1,400 |
| Prepared eligible remainder | 3,901 |
| Revalidation batches | 16 |
| RB published products | 16,415 |
| RB products with displayable local media | 8,214 (50.04%) |

## Exclusions

The source slice contains 203 non-safe records that were not attached:

- 20 duplicate candidates;
- 3 linked-identity candidates;
- 180 1C collision holds.

Two additional safe draft candidates have no `PREVIEW_PICTURE` or
`DETAIL_PICTURE` reference in the Bitrix snapshot. They remain without an image
instead of receiving a similar-looking asset.

## Verification

- manifest: 5,301 exact media references and 5,301 unique selected files;
- archive extraction: 5,301 assets, zero rejected;
- PostgreSQL: 8,214 / 16,415 published RB products have displayable media =
  50.04%;
- mobile category: 5,303 published, 1,400 with media, zero priced and zero
  indexable products;
- next importer dry-run: exactly 3,901 prepared eligible products remain;
- browser: 12 / 12 first-page images loaded with non-zero dimensions, zero
  broken images and zero placeholders;
- visual review: sampled cards showed product-relevant battery images;
- sample `/api/media/6831`: HTTP 200, `image/jpeg`, private/no-store and
  `X-Robots-Tag: noindex, noarchive`;
- Horizon logs show all 16 observed revalidation jobs completed.

## Safety boundary

These assets have status `legacy_exact_preview`. They are allowed only on
noindex catalogue previews because they are linked to the exact same Bitrix
element but have not all received manual visual model verification. The wave
does not infer identity, characteristics, price, stock or SEO indexability.

## Next efficient step

The remaining 3,901 mobile images are already extracted and stored. The next
coverage milestone can therefore attach bounded batches without reading the
Bitrix archive again. Strict SEO readiness remains a separate evidence gate.
