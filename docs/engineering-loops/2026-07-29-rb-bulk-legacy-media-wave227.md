# RB bulk company-owned legacy media — Wave227

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope and no-repeat boundary

Wave227 started from the 1,486-card Wave226 enrichment queue. The live read-only exporter selected only published site products with an exact product MPN, a company-owned `legacy_exact_preview`, a pinned storage path and SHA-256, and no prior Wave225/Wave226 review key. It never used a filename or product title to invent identity.

The preliminary profile found a smaller 102-row subset. It was superseded before production by the stricter live Laravel exporter, which validated **304 unique product/media rows** against the current database. The supersession is recorded in the preliminary profile artifact.

## Duplicate and identity gates

- exporter rows: **304**;
- unique content hashes: **272**;
- shared-image rows held before OCR: **47** across 15 repeated hash groups;
- unique-image rows admitted to OCR: **257**.

The repeated images include the same generic UPS or battery picture attached to several distinct MPNs. All rows in every shared-hash group were held; none was allowed to borrow identity from another product.

## OCR and visual review

The 257 unique assets were materialized from the local company-owned Bitrix media volume in one archive. All 304 exported files, including held duplicates, matched their pinned SHA-256.

OCR ran in deterministic batches of **100 + 100 + 57**:

- OCR PASS: **75**;
- OCR HOLD: **182**;
- decode, file, language or async errors: **0**.

All 75 OCR-PASS images were rendered into seven frozen contact sheets and visually inspected. The exact MPN is readable on every approved image. The small `bitrix:10834` laptop-battery label was additionally checked at original resolution and visibly contains `00HW025`.

## Application

- manifest builder tests: **2 passed**;
- OCR batch-builder tests: **3 passed**;
- PowerShell materializer and runner static safety tests: **passed**;
- promotion dry-run: **75/75 passed**;
- apply: **75 promoted**, **75 SiteProduct rows touched**;
- database verification: **75 verified and published Wave227 media rows**;
- product publication changes: **0**;
- price, availability and other commercial changes: **0**.

Of the 75 products, 23 already had an applied source-backed description and became content-complete immediately. The remaining 52 now have a verified image but still require source-backed description research.

## Readiness result

- content-complete cards: **156 → 179**;
- verified content-complete share: **1.0905%** of the fixed 16,415-card denominator;
- `strict_content_ready`: **41 → 64**;
- remaining cards to the fixed 10% target: **1,463**;
- SEO audit: **16,853 URLs**, **97 redirects**, **0 blockers**.

The catalogue passed the verified 1% content-complete mark, but did not cross a project-level 10-point milestone. Overall project readiness remains 60%.

## Evidence

- `docs/audits/generated/rb-wave227-legacy-preview-candidates.csv`;
- `docs/audits/generated/wave227-ocr-batches/index.json`;
- `docs/imports/rb-reviewed-legacy-preview-media-wave227-2026-07-29.json`;
- `docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.csv`;
- `docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.summary.json`;
- `docs/audits/generated/wave227-media-promotion-receipt.json`;
- `docs/audits/generated/rb-full-content-readiness-wave227-after.csv`;
- `docs/audits/generated/rb-enrichment-queue-wave227.csv`.

No commit or push was performed.
