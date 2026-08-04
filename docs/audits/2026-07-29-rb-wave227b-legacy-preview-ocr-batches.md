# Wave227-B: chunked legacy-preview OCR review

`build-rb-wave227-ocr-batches.py` consumes only the read-only CSV produced by `media:export-enrichment-legacy-preview-candidates`. It never derives an expected marking from a product name or file name. It accepts `identity_scope: exact` only with an exact MPN, and `identity_scope: model_core` only with a model core and manufacturer. An image is eligible only when its materialized local SHA-256 matches the exporter row.

The builder excludes a media record if its external-ID/media-ID pair, media ID, or content hash has already appeared in either reviewed-media manifest from Wave225 or Wave226. Eligible records are sorted by external ID and media ID, then split into fixed-size UTF-8-with-BOM OCR input CSV chunks. With the expected 102 safe exporter rows and the default chunk size of 100, the plan is deterministically 100 + 2. `run-rb-wave227-ocr-batches.ps1` runs the existing local OCR helper once for each indexed chunk and fails rather than overwriting an existing review CSV.

Within the current exporter batch, a content SHA-256 may belong to only one product and one expected identity. If a hash occurs with multiple external IDs or expectations, every row with that hash is held as `shared_asset_hash_across_products`, including separate products that happen to have the same exact MPN. It is not sent to OCR.

## Current production plan

The current `rb-wave227-legacy-preview-candidates.csv` export has 304 rows. After materializing only those files from the local backend media volume and verifying every SHA-256, 47 rows were held by the current-batch shared-hash guard. The remaining 257 exact-identity assets are in deterministic OCR inputs of 100 + 100 + 57. This is a review plan only; OCR has not been invoked and no media state has changed.

`materialize-rb-wave227-ocr-assets.ps1` creates an archive of only the exported `storage_path` values in the backend container, transfers it with `docker cp`, and verifies each extracted SHA-256 under `.tmp/wave227-assets`. It performs one `docker compose exec` archive operation and no per-file network calls.

Neither tool accesses a database, changes publication/media state, auto-passes OCR, or promotes an image. OCR outputs remain review evidence for a separate human decision.

## Final execution status

This preparation report is superseded by the completed Wave227 loop in `docs/engineering-loops/2026-07-29-rb-bulk-legacy-media-wave227.md`. The production exporter contained 304 rows; 47 shared-hash rows were held, OCR ran for 257 unique assets, 75 passed OCR and visual review, and those 75 were promoted by the separate strict promotion command. This batch builder and its runner themselves remained read-only and performed no database mutation.
