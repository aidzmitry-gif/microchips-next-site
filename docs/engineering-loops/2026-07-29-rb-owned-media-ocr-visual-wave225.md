# RB company-owned media OCR and visual review — Wave225

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope

The 334 Wave224 source-backed products were checked for media. Exactly 125 had a displayable company-owned `legacy_exact_preview` image and 209 had no preview asset. No external image was downloaded or copied.

The 125 local assets were exported from the application media volume with their exact ProductMedia ID, storage path, SHA-256 and company-owned rights basis. Every exported file matched the pinned hash.

## OCR gate

A Windows PowerShell 5.1 helper uses the local `en-US` and `ru-RU` Windows.Media.Ocr engines. It receives the expected MPN/model core from the manifest and never derives identity from a filename.

The first real run exposed a WinRT generic `AsTask<TResult>` bridge error. It failed closed: all 125 rows became HOLD and no media status changed. The bridge was corrected and tested on a real raster before the full rerun.

Final OCR result:

- PASS: 48;
- HOLD: 77;
- decode, file, language or async errors: 0;
- every HOLD reason: exact bounded expected token sequence not found.

## Visual review

The 48 OCR-PASS images were rendered into four frozen contact sheets. Each image was visually inspected at original sheet resolution. All 48 are Panasonic product photographs whose visible marking matches the expected exact model core; packaging multipacks remain tied to their exact legacy Bitrix element and were not generalized to other products.

The promotion manifest pins the exact OCR input, OCR output and contact-sheet index by SHA-256. A future file change invalidates the builder rather than silently reusing the decision.

## Application

The new `media:promote-legacy-exact-preview-media` command validates the current ProductMedia ID, product/site relation, current preview status, storage path, actual asset hash, company-owned rights, exact identity boundary, evidence level and review date. Its default mode is dry-run.

- dry-run: 48/48 passed;
- apply: 48 promoted and 48 SiteProduct rows touched;
- DB verification: 48 are now `verified`, published and retain company-owned rights;
- product publication changes: 0;
- price/availability/commercial changes: 0.

## Readiness result

- content-complete cards (description + verified image): **88 → 136**;
- remaining rows to the fixed 10% target: **1,506**;
- narrower `strict_content_ready` class: **41** (unchanged, because it also requires stable identity and technical gates);
- SEO audit: 16,853 URLs, 97 redirects, 0 blockers.

This is measurable progress toward the 10% catalogue-content milestone, but it is only 48 of the required 1,554 additional complete cards. The project percentage therefore remains 60%.

## Evidence

- `docs/audits/generated/rb-wave225-ocr-input.csv`;
- `docs/audits/generated/rb-wave225-ocr-review.csv`;
- `docs/imports/rb-reviewed-legacy-preview-media-wave225-2026-07-29.json`;
- `docs/audits/generated/wave225-media-promotion-receipt.json`;
- `docs/audits/generated/rb-full-content-readiness-wave225-after.csv`;
- `docs/audits/generated/rb-enrichment-queue-wave225.csv`.

No commit or push was performed.

