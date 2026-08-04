# RB Bitrix staging transfer — waves 138–140

## Outcome

The current `microchips.by` battery/power catalogue was preserved in Laravel
as a complete, non-renderable staging snapshot before cleanup. The operation
did not create missing 1C products, publish pages, render legacy HTML, or alter
the existing public catalogue.

## Source extraction

- Read-only Bitrix snapshot: `2026-06-23`.
- Broad selected catalogue slice: **2,856** products.
- Confirmed first-focus denominator: **1,569** products:
  - 1,445 through the primary section;
  - 81 through another selected section;
  - 43 through additional membership with a primary section outside the slice.
- Legacy content evidence:
  - 1,569/1,569 focus rows have detail text;
  - 1,568/1,569 have a preview or detail media reference.
- Offer iblocks 28/67 gate passed: 12 known orphan footwear offers, 0
  unreviewed offers and 0 catalogue parent links.

The extractor now writes
`docs/audits/generated/bitrix-b2b-catalog-content.csv`. Legacy HTML is stored
only as untrusted evidence and is never rendered directly.

## Identity and staging manifest

Authoritative identity input:
`docs/imports/rb-1c-match-v2-matched.csv` — 596 mapped legacy rows to 248
unique 1C products. A stale external CSV with only 37 unique focus identities
was detected and rejected during the first build.

Final manifest:
`docs/imports/rb-bitrix-staging-transfer-wave138-2026-07-28.json`.

Status distribution:

- 79 `strict_mapped_evidence`;
- 78 `candidate_mapped_evidence`;
- 430 `candidate_duplicate_group`;
- 973 `hold_missing_1c_identity`;
- 2 `hold_missing_rb_site_product`;
- 1 `scope_excluded_electronics`;
- 6 `excluded_inactive_legacy`.

Laravel staging import:

- 1 import run;
- 1,569 `staged_import_records`;
- 0 staged rows published;
- repeated apply returned `unchanged=true` for the same SHA-256 manifest.

## Legacy category tree

- 219 Bitrix sections imported under source `bitrix_sections`;
- 220 Bitrix-source categories now exist in the database: 219 from this
  snapshot plus one pre-existing category outside the imported manifest;
- all 219 remain unpublished;
- repeated apply: 219 unchanged;
- 252 product/category assignments preserved for 245 existing 1C products;
- 240 new links and 12 already-existing links on first apply;
- repeated apply: 252 unchanged.

The old tree is staging evidence. It is not the final SEO taxonomy and is not
exposed to indexation.

## Public-state safeguards

- RB published site products remained **233**;
- 12/12 published category previews retain reviewed descriptions;
- `seo:audit microchips-by --json`: pass, 261 checked URLs, 0 blockers;
- public `/catalog`: HTTP 200;
- no legacy staging record has `published_at` or `published_product_id`.

## Verification

- extractor self-test passed on PowerShell 5.1;
- full extractor completed with first-focus count 1,569;
- Python builder test passed;
- Laravel feature test for snapshot staging passed;
- Pint passed for the command, feature test and Filament resource;
- dry-run → apply → idempotency checks passed for the snapshot, category tree
  and category assignments.

## Still required before calling the old site visibly transferred

1. Add a noindex preview surface for the imported snapshot; it must sanitize
   legacy HTML and remain separate from canonical products.
2. Preserve non-product commercial pages and documents from the old site.
3. Only after the visual snapshot is complete, start duplicate collapse,
   taxonomy correction and manufacturer enrichment.

## Media staging continuation

- 1,568 unique `b_file` references resolved against the validated Bitrix dump;
- 1,568 raster files extracted and verified with Pillow;
- total staged size: 263,789,635 bytes;
- one legacy row (`2389`) has no media reference;
- assets copied to the persistent Docker media volume under
  `legacy-staging/rb`;
- 0 assets assigned to canonical `product_media` records.

Evidence:
`docs/audits/generated/rb-bitrix-staging-media-wave141.csv` and
`docs/audits/generated/rb-bitrix-staging-media-wave141-summary.json`.

Search Console and Yandex Webmaster could not be read because browser security
blocked their account-login domains. CSV exports of queries and pages can be
added later without blocking the transfer.
