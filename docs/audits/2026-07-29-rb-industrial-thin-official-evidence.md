# RB industrial thin-card official evidence — wave 171

Date: 2026-07-29. Site: `microchips-by`.

## Scope

This review closes the official-source investigation of the seven published
noindex industrial-battery previews that had neither usable source text nor
company-owned media after wave 170. It does not alter prices, stock,
publication, indexability or product identity.

The pinned source is
`docs/audits/generated/rb-missing-description-research-queue-wave170.csv`,
SHA-256
`f5a8b65533bddbeea86d2b9159ed6595f5a2bc45141de9b3793d4f0b0c583d63`.

## Result

| Result | Cards |
| --- | ---: |
| Exact official identity established | 0 |
| Identity conflict proved | 4 |
| Still requires a primary source | 3 |
| Safe description drafts | 0 |
| Safe image imports | 0 |
| Safe automatic merges | 0 |

This is not a failed enrichment pass. The official evidence prevents four
incorrect catalog changes:

- treating aftermarket-looking `BT-26`, `BT-0016` or `BSB-005` tokens as
  Datalogic OEM part numbers;
- replacing the Skorpio `6800 mAh` claim with an official `6700 mAh` accessory
  without proving that both refer to the same pack;
- publishing `5200 mAh` for Omnii when Zebra documentation says `5000 mAh`;
- merging Psion and Zebra cards or combining MC30xx and MC31xx battery families
  solely from similar compatibility titles.

The complete per-card source record is
`docs/audits/generated/rb-industrial-thin-official-evidence-wave171.json`.

## Image decision

No battery image was imported. Official device imagery is not evidence of the
offered replacement battery, and no reviewed official source supplied both an
exact pack identity and reusable image rights. Zebra explicitly restricts
reuse of its product photography in its
[copyright policy](https://www.zebra.com/us/en/about-zebra/company-information/legal/copyright.html).
The reviewed Datalogic PDFs also carry restrictive copyright notices.

Company-owned photography, a supplier label/photo tied to the exact ordered
P/N, or a licensed partner media kit can clear these holds later.

## Storefront disposition

The seven records remain noindex research previews. Four are classified as
`identity_conflict`; three remain `needs_primary_source`. No unsupported
technical fact, image or duplicate merge was applied.

The next enrichment wave moves to the 113 image-backed, text-missing cards in
source-specific groups so that exact identity can be checked in batches
without slowing the already-complete Bitrix migration.
