# RB B2B exact-media closure — Wave 235

Date: 2026-07-29  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

The current enrichment queue was processed through the existing company-owned Bitrix media lane without repeating identity or description research:

| Gate | Rows | Result |
|---|---:|---|
| Exported exact-identity candidates | 117 | Complete bounded input |
| Shared asset hashes | 47 | HOLD; one binary cannot prove several product identities |
| Unique binaries sent to OCR and machine vision | 70 | Complete visual coverage in seven contact sheets |
| Exact MPN visibly confirmed at original resolution | 9 | PASS and promoted |
| Remaining reviewed rows | 108 | HOLD; exact model absent, ambiguous, unreadable, or binary reused |

The nine promoted images are tied to `bitrix:11753`, `bitrix:1464`, `bitrix:1493`, `bitrix:1526`, `bitrix:1561`, `bitrix:1617`, `bitrix:24551`, `bitrix:2952`, and `bitrix:4776`. Each image has a unique SHA-256 binary, a company-owned legacy rights basis, an exact product identity and a complete MPN visible on the pictured item.

No APC or generic EnerSys chassis image was promoted merely because its filename or product title matched. The known General Security mismatches also remained on HOLD.

## Application evidence

- Manifest: `docs/imports/rb-reviewed-legacy-preview-media-wave235-2026-07-29.json`
  - SHA-256: `b67244c09140e7c037d445b49a13022b03262a13f839a7ce5d67bebb4240da14`
- Dry-run: 9 records, 0 changes.
- Apply: 9 promoted, 9 site products touched, 0 publication changes, 0 commercial changes.
- Database confirmation: all nine pinned media IDs have `verification_status=verified`, remain published and have `verified_at` populated.
- A second apply was deliberately refused by the command's one-shot `legacy_exact_preview` precondition after the first successful promotion. Final database state, rather than the rejected replay, is the authoritative success check.

## Verified progress

- Content-complete published cards: **381 → 384** (`+3`).
- Strict-content-ready cards: **202 → 205** (`+3`).
- Remaining 10% enrichment queue: **1261 → 1258** (`-3`).
- Readiness distribution: 14,672 legacy content previews; 103 preview-only; 923 text-only; 906 source-backed partial; 205 strict-ready; 7 thin unidentified.
- SEO audit: **16,853 URLs**, **97 redirects**, **0 blockers**.
- Commercial state unchanged: 57 current numeric prices; all 24,348 site products remain `on_request`.
- Python deterministic/fail-closed tests: **2 passed** (Wave234-F regression plus Wave235).
- HTML prototype gates: **4 passed**.

Nine promoted images only lifted three cards to strict-ready because six cards still lack another mandatory content component, normally a source-backed description. This is expected and is recorded rather than counted as completed content.

## Next step

Process the 1,258-row queue description-first for products that already have verified media, then use manufacturer-primary evidence to close both missing content gates in one batch. Shared binaries remain quarantined until an exact replacement image with a valid rights basis is available.
