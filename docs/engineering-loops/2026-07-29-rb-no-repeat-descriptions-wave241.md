# Wave241 — no-repeat descriptions and media-gap closure

Date: 2026-07-29  
Site: `microchips-by`

## Result

Wave241 reconciled every one of the 1,247 records remaining in the Wave240 enrichment queue without repeating prior research.

- 745 records already had an applied description and lacked a verified published image:
  - 116 were linked to an existing media decision;
  - 629 were placed in explicit acquisition HOLD because no new local, exact, reusable-rights raster candidate exists;
  - 0 images were promoted on weak identity or rights evidence.
- 502 records lacked both an applied description and a verified published image:
  - 458 were deterministically linked to existing identity HOLD decisions;
  - 44 identified records were isolated for new description work;
  - 0 previously processed description rows were replayed.
- The 44 actionable rows were matched to SHA-pinned manufacturer-primary PDF/HTML snapshots:
  - exact model present: 44/44;
  - source technology marker present: 44/44;
  - prior description manifests scanned: 14, containing 337 rows;
  - overlap with prior rows: 0.

## Adversarial gate

The first Laravel dry-run rejected the preliminary manifest because manufacturer-primary `model_core` evidence requires a verified `technology`. Nothing was written by the failed dry-run. The builder was corrected before apply:

- technology is now an explicit fail-closed series/model rule;
- the same pinned primary snapshot must contain the expected technology marker;
- unsupported manufacturer/model combinations stop generation;
- HOLD rows cannot enter the manifest;
- UTF-8 tests reject U+FFFD and common mojibake markers.

Final technology distribution: `VRLA AGM` 15, `AGM` 15, `GEL` 8, `VRLA GEL` 1, `lead-acid` 5.

## Apply evidence

- Final manifest SHA-256: `35c66fcc25b52bc7f36071d788431fe87f0e42e9d00abd4bf1f1d69b2db34ca5`.
- Stage run 1043: 44 refreshed, 0 published.
- Apply dry-run 1044: 44 validated; publication changes 0; commercial-field changes 0.
- Apply run 1045: 44 applied; publication changes 0; commercial-field changes 0.
- Idempotence runs 1047/1048: 44 refreshed for revalidation, then 0 applied and 44 unchanged.
- Latest 44 draft rows: 44 distinct products, all status `applied`.

Commercial control snapshot was identical before and after apply:

| Metric | Before | After |
|---|---:|---:|
| Site products | 24,298 | 24,298 |
| Published | 16,816 | 16,816 |
| Numeric prices | 1,067 | 1,067 |
| Price sum | 1,616,436.49 BYN | 1,616,436.49 BYN |
| Availability `on_request` | 24,298 | 24,298 |

Runtime evidence for `bitrix:1145` resolves at `/catalog/industrial-batteries/batteries-ups/legacy-bitrix-1145` with the applied Panasonic model, `VRLA AGM`, price `828.00 BYN`, availability `on_request`, and its existing media. The page remains `noindex`; Wave241 did not use description enrichment to bypass the publication/SEO gate.

## Readiness after Wave241

- Content-complete cards: 395 (unchanged; this wave intentionally did not invent or promote images).
- Strict-content-ready: 216 (unchanged).
- `source_backed_partial`: 924 -> 968 (+44).
- Remaining enrichment queue: 1,247:
  - description present / image missing: 789;
  - description missing / image missing: 458.

Overall confirmed project readiness remains 60%. Wave241 improves evidence quality and closes 44 description gaps, but it does not justify a project-level +10 percentage-point claim.

## Verification

- Python Wave241 suite: 6 passed in 135.35s.
- Python builders: `py_compile` passed; `git diff --check` passed.
- SEO release audit: 16,853 URLs, 97 redirects, 0 blockers.
- RB prototypes: 4/4 passed.
- Docker: PostgreSQL, Redis, backend, worker, frontend and nginx running; backend was rebuilt from the current worktree before apply.

## Evidence files

- `docs/imports/rb-source-backed-descriptions-wave241-2026-07-29.json`
- `docs/audits/generated/rb-wave241-source-backed-descriptions-ledger.csv`
- `docs/audits/generated/rb-wave241b-media-acquisition-hold-ledger.csv`
- `docs/audits/generated/rb-wave241c-description-image-no-repeat-ledger.csv`
- `docs/audits/generated/rb-enrichment-queue-wave241.csv`
- `docs/audits/generated/rb-full-content-readiness-wave241-after.csv`

No commit or push was performed.
