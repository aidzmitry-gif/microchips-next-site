# RB Saft/FANSO legacy media candidates — 2026-07-27

## Scope

Read-only audit of company-held legacy Bitrix media as a possible source of
image candidates for the 77 Saft/FANSO products in description waves 79 and
80. No files were extracted, imported, published, or attached to products.

Sources checked:

- `docs/audits/generated/full-catalog-canonical-registry.csv`;
- `docs/imports/rb-source-backed-description-drafts-saft-model-core-wave-79-2026-07-27.json`;
- `docs/imports/rb-source-backed-description-drafts-fanso-model-core-wave-80-2026-07-27.json`;
- `D:\6 Проекты\microchips.by\db\user_microchips_data.sql.gz`;
- `D:\6 Проекты\microchips.by\microchips_upload_20260623.tar` (`_shared/upload`).

## Result

- The 77 wave rows have **no exact 1C-code link** to a legacy Bitrix element.
- Brand plus normalized model-core matching produced **48 legacy Bitrix
  elements**: 47 Saft elements covering the eight audited Saft cores and one
  FANSO `ER34615H/S` element.
- The remaining **26 FANSO rows have no legacy model-core media candidate**.
- All 48 elements contain both `PREVIEW_PICTURE` and `DETAIL_PICTURE`: **96
  `b_file` references** in total. All requested references resolved to a
  `b_file` record.
- The backup tar contains the expected `_shared/upload` tree. Representative
  spot checks for FANSO, LS14250, and LS33600 paths were present. A full archive
  extraction or 96-file import was deliberately not performed.

## Classification and limits

These links are **model-core representatives only**, not automatically
approved exact-variant images. Several different legacy variants point to the
same physical media path (including examples in the LS14250, LS14500, LS26500,
and LSH20 families). Without an exact 1C identity link and visual review, the
attachment cannot prove the pictured terminal, connector, lead, bundle, or
other configuration.

The backup establishes that the files were used by the company's legacy
Bitrix site. It does **not** by itself establish the original photographer,
supplier permission, or reusable third-party licence for every image.
Therefore legacy files may enter a controlled migration review as candidates,
but must not be labelled licence-cleared or published automatically.

## Safe next gate

For any later media migration, require all of the following before publication:

1. exact product/configuration match confirmed visually;
2. duplicate media paths and generic family images identified;
3. provenance or business authorization recorded;
4. image quality, dimensions, branding, and misleading accessories reviewed;
5. only the approved file copied from the archive and attached to the intended
   product.

