# RB primary-source editorial drafts — 2026-07-27

## Scope and safety boundary

This batch creates editorial review drafts only. It does not update canonical
product fields, publish a product, create an Offer, or authorize use of an
image. A product can become public only after the separate identity,
commercial-data, media-rights and SEO gates pass.

## Primary evidence used

| 1C external ID | Product identity in source | Primary source | Facts staged |
|---|---|---|---|
| `КА-00004377` | Panasonic BR2330 | [Panasonic specification PDF](https://industrial.panasonic.com/cdbs/www-data/pdf2/AAA4000/AAA4000C230.pdf) | 3 V, 255 mAh, dimensions, operating temperature and intended low-drain memory-backup use |
| `КА-00003325` | OMRON CJ1W-BAT01 | [OMRON CJ2M specification](https://www.ia.omron.com/products/family/2712/specification.html) | compatible-controller purpose, 5-year service life at 25 °C and approximate mass |
| `ФР-00002108` | FIAMM 12FGH36 | [FIAMM FGH-series catalogue](https://www.fiamm.ru/equipment/FGH-series/) | 12 V, 9 Ah, dimensions, mass and F2 Faston terminal |

The title/MPN correspondence was checked against the stable 1C external ID.
The importer permits source evidence where legacy structured `manufacturer`
and `mpn` fields are blank, but still rejects any disagreement with a
non-empty catalogue identity.

## Database verification

- Import run 81 (dry run): 2 records validated, 0 publications.
- Import run 82 (apply): 2 `product_description_drafts` created.
- Import run 83 (dry run): one additional FIAMM record validated; existing
  drafts stayed unchanged.
- Import run 84 (apply): one FIAMM `product_description_draft` created.
- All three records have status `draft` and retain their source URLs.
- No `site_products.is_published` values were changed.

## Next batch rule

Do not group terminal variants, battery assemblies or OEM replacements under a
base-cell source. Each needs its own exact MPN and its own primary source
before it can receive a draft. Image collection is a separate rights and
visual-match ledger; no image is imported from a retailer page.
