# RB B2B identity, content and media closure — Wave 234

Date: 2026-07-29  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

The 164 previously unreviewed B2B identity/media-gap rows were partitioned without overlap and reviewed without repeating Wave233 work:

| Lane | Rows | Applied PASS | HOLD | Result |
|---|---:|---:|---:|---|
| Panasonic / MNB | 56 | 0 | 56 | 55 no exact saved primary evidence; 1 conflict |
| APC / EnerSys | 34 | 0 | 34 | 25 no exact evidence; 8 conflicts; 1 family-level compatibility only |
| General Security | 37 | 29 | 8 | 29 exact collision-free models; 4 suffix holds; 2 absent models; 2 normalizer collisions |
| Other residual brands | 37 | 0 | 37 | 13 prior fail-closed reviews; 24 without pinned exact primary proof |
| **Total** | **164** | **29** | **135** | every row has an explicit decision |

The first General Security manifest contained 31 exact official headings. Laravel dry-run correctly rejected it because `GSL 1.2-12` and `GSL 12-12` both normalize to `gsl1212`. Neither was selected arbitrarily. The rebuilt 29-row manifest passed dry-run, applied 29 identities, and produced 29 `unchanged` on the idempotency run. Price, availability and publication counters stayed at zero changes.

Source-backed descriptions were applied to 28 rows. `bitrix:2849` retained its prior description because its legacy title has extra commercial words after the exact MPN and therefore failed the strict manufacturer-primary title gate.

All 29 company-owned legacy images were SHA-verified and reviewed with Windows OCR plus machine-vision contact sheets. Twenty-six exact images were promoted. Three wrong legacy images were detected and held:

- `bitrix:3034`: expected `GSL 40-12`, visible label `GS 40-12`;
- `bitrix:3135`: expected `GSL 65-12`, visible label `GS 65-12`;
- `bitrix:3268`: expected `GS 9-12`, visible label `GSL 7.2-12`.

## Evidence and safeguards

- Official General Security catalogue snapshot: `docs/audits/sources/wave234c/general-security-product.html`
  - SHA-256: `9b3d5c6276c1df6b751233e78875449241a504fb36a010e603b1d0648f17f400`
- Exact model matching preserves series and numeric model identity.
- Terminal suffixes `F1` / `F2` are not inferred from a base-model heading.
- APC/EnerSys and Panasonic/MNB reuse prior evidence ledgers instead of repeating network research.
- All unresolved identities and mismatched images remain HOLD.
- Final database audit: 29 identified General Security products; 28 manufacturer-primary applied descriptions plus 1 legacy description; 26 verified images plus 3 legacy-preview images; 29 `on_request`; 0 prices.

## Verified progress

- Content-complete published cards: **356 → 381** (`+25`).
- Strict-content-ready cards: **177 → 202** (`+25`).
- Remaining 10% enrichment queue: **1301 → 1261** (`-40`, including newly identified rows no longer blocked at the same stage).
- SEO audit: **16,853 URLs**, **97 redirects**, **0 blockers**.
- Commercial audit: 57 legacy price-evidence rows, 0 eligible 1C prices, 0 database mutations.
- Python tests: **8 passed**.
- HTML prototype gates: **4 passed**.
- Targeted runtime dry-runs and applies passed against PostgreSQL. The production Docker image has no PHPUnit development dependency; local PHPUnit was also unavailable because local PHP lacks `mbstring`, so no PHPUnit result is claimed.

## Next step

Continue with the next 1,261-row enrichment queue in large deterministic batches. Prioritize rows that already have exact identity and company-owned media, while quarantining wrong-image clusters before description work. The three visual mismatches require a replacement image with a valid rights basis or must keep their current non-strict preview state.
