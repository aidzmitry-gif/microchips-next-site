# Wave242-C official-source image audit

The 44 products from the Wave241 description manifest were checked only against their already SHA-pinned manufacturer-primary HTML/PDF evidence. Their company-owned legacy images were not reviewed again: 39 have Wave235 `HOLD`, five retain earlier Wave229B/229C HOLD/REJECT evidence, and all 44 are pinned by the Wave237 no-repeat ledger.

## Result

- PASS: **0**; no promotion manifest was created.
- HOLD: **44**.
- Official visual candidates: **37** (33 rendered PDF pages and 4 unique APC rasters).
- Every pinned official source lacks a documented image-reuse grant for Microchips. Manufacturer ownership/public availability is not permission to republish commercially.
- APC RBC17 and RBC40 share the same official raster, so that asset is not exact-model evidence for either product.

The audit-only extracts remain under the ignored `docs/audits/generated/rb-wave242c-official-image-audit/` zone. They are evidence, not publishable media.

## Artifacts

- `docs/audits/generated/rb-wave242c-official-image-ledger.csv` — full 44-row decision ledger.
- `docs/audits/generated/rb-wave242c-official-image-candidate-index.csv` — page/raster hashes and contact-sheet pins.
- `docs/audits/generated/rb-wave242c-official-image-audit.summary.json` — deterministic counters and input/output hashes.

No database query, database mutation, media apply, publication action, or commit was performed.
