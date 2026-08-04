# Wave232-C: MNB exact-media replacement evidence — HOLD

Checked: 2026-07-29. This record is evidence-only. It creates no media
manifest, does not download external assets, and does not change the database.

## Decision

Both targets remain **HOLD**. Their catalogue identities are independently
source-backed, but no SHA-pinned, company-owned local image with the complete
expected MPN was found. An official MNB product page is a good *identity*
source and a possible future image source; it is not evidence that Microchips
has permission to copy or publish the page's image asset.

| Target | Expected exact MPN | Current company-owned asset, visually checked | Local exact replacement result | Decision |
| --- | --- | --- | --- | --- |
| `bitrix:3099` | `MR 55-12FT` | media `821`, `legacy-staging/rb/bitrix-3099-79562.jpg`, SHA-256 `69d30d4d6d0dd0af96412e8340e26fd4feca18b456e3f99e7a0e24ad5678caad`; the label visibly reads `MR 80-12FT` | No exact candidate in current `product_media` or materialized backup files | HOLD — leave media `needs_review` and unpublished |
| `bitrix:3219` | `MM 75-12` | media `915`, `legacy-staging/rb/bitrix-3219-79558.jpg`, SHA-256 `acc7e945a13696dc3f60afad0e0f384d3e3820c35cd9cceb1e9d0edc8aafb166`; the label visibly reads `MM55-12` | No exact candidate in current `product_media` or materialized backup files | HOLD — leave media `needs_review` and unpublished |

The visual readings above were made from the two SHA-pinned local assets. They
also reproduce the Wave231-B mismatch findings; neither image is transferable
to another product merely because it depicts an MNB battery.

## Local provenance and duplicate search

The current database has exactly one media row for each target. Each content
SHA is used once, so neither has an already-linked duplicate asset:

| Target | Current media id | SHA uses | Same-MPN `products` / `product_media` duplicate |
| --- | ---: | ---: | --- |
| `bitrix:3099` | `821` | 1 | none |
| `bitrix:3219` | `915` | 1 | none |

The full Bitrix media index contains same-name legacy elements, but not a
reusable, materialized asset in this workspace or current database:

| Full Bitrix element | Exact catalogue name | Original file references | Why it is not a manifest candidate |
| --- | --- | --- | --- |
| `29583` | `MNB MR 55-12FT` | preview `98357`, detail `98358` | Binary is not present in the checked backup/materialized-files set; no current product/media row, storage path, or SHA-256 can be pinned or visually reviewed. |
| `29497` | `MNB MM 75-12` | preview `98185`, detail `98186` | Binary is not present in the checked backup/materialized-files set; no current product/media row, storage path, or SHA-256 can be pinned or visually reviewed. |

The index's element-to-file relation establishes neither an available asset nor
an exact visible-MPN review. It must not be converted into a promotion manifest
from file IDs alone.

## Official MNB identity evidence and image candidates

The existing pinned MNB catalogue snapshot is the identity source:

- publisher: MNB Battery;
- snapshot: `docs/audits/sources/wave206-panasonic-ventura-mnb/mnb-official-catalogue.pdf`;
- SHA-256: `85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859`;
- text confirms `MNB MR 55-12 FT`, 12 V / 55 Ah, and `MNB MM 75-12`, 12 V / 75 Ah.

The live official product pages were also read on 2026-07-29. They agree with
the expected model, series, voltage, and capacity and expose product-image
URLs. The URL spelling `MR 55-12 FT` is the official presentation of the
catalogue MPN normalized in Microchips as `MR 55-12FT`.

| Target | Official model page | Official candidate image URLs | Rights status |
| --- | --- | --- | --- |
| `bitrix:3099` | [MR 55-12 FT](https://mnb-battery.ru/catalog/lead/rm-ft/mr-55-12ft/) | [right 45°](https://mnb-battery.ru/img/products/mr/mr_55-12ft_right45.JPG), [left 45°](https://mnb-battery.ru/img/products/mr/mr_55-12ft_left45.JPG), [front](https://mnb-battery.ru/img/products/mr/mr_55-12ft_front.JPG) | `HOLD_external_manufacturer_asset_no_reuse_license` |
| `bitrix:3219` | [MM 75-12](https://mnb-battery.ru/catalog/lead/m-m/mm-75-12/) | [right 45°](https://mnb-battery.ru/img/products/mm/mm_75-12_right45.JPG), [left 45°](https://mnb-battery.ru/img/products/mm/mm_75-12_left45.JPG), [front](https://mnb-battery.ru/img/products/mm/mm_75-12_front.JPG) | `HOLD_external_manufacturer_asset_no_reuse_license` |

No licence, distribution agreement, written permission, or existing
Microchips ownership link was found for these external assets. Therefore the
URLs are reference-only: they must not be downloaded into the catalogue, given
a `rights_basis`, or marked verified on the strength of public availability.

## Exit criteria

A future exact-media manifest is permitted only after all of the following are
available for each target:

1. a company-owned Bitrix backup binary or written MNB/distributor permission
   that explicitly permits Microchips catalogue use;
2. a stored local asset with a deterministic storage path and SHA-256;
3. a human visual review establishing the complete visible expected MPN (not
   capacity, series, or model-core similarity); and
4. a manifest/test that pins the current product MPN, source/rights evidence,
   asset hash, and exact-MPN review before any separately authorized apply.

Until then, no `PromoteLegacyExactPreviewMedia` or source-image import manifest
is safe for these two targets.
