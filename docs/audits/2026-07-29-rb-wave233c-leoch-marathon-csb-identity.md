# Wave233-C: identity review for Leoch, Marathon, and CSB UPS batteries

Date: 2026-07-29  
Scope: 131 blank-manufacturer UPS rows from `rb-wave233-identity-media-gaps.csv` only.

## Result

There are no PASS rows and the accompanying identity manifest intentionally has an empty `products` array. This is a valid fail-closed result, not a request to infer missing identity fields.

| Manufacturer | Rows | PASS | HOLD |
| --- | ---: | ---: | ---: |
| Leoch | 50 | 0 | 50 |
| Marathon | 49 | 0 | 49 |
| CSB | 32 | 0 | 32 |
| Total | 131 | 0 | 131 |

All source SKUs are blank. Candidate MPNs are deterministically taken from the text after the brand and before the technical parenthesis; normalization is Unicode NFKC upper-case with non-alphanumerics removed. The ledger checks the normalized manufacturer+MPN as well as SKU.

## Evidence and holds

- The saved CSB manufacturer PDF for `bitrix:1418` is SHA-pinned and proves `HRL12390W`, but the offered name is `HRL12390W FR`; the earlier Wave206 evidence explicitly records this suffix conflict. It remains HOLD.
- The prior local Wave145 decision file has four CSB URL assertions (`1796`, `2777`, `3027`, `3258`), but contains no immutable local official snapshot. They are therefore audit context only, never PASS evidence.
- Saved CSB and Leoch generated model registries have no exact match for a target model once suffixes are retained. Marathon has no saved immutable first-party source in the supplied evidence set.
- `bitrix:25828` and `bitrix:25830` both normalize to `Leoch / FT1240`; both are HOLD pending duplicate adjudication.

No database, media, price, stock, publication, SEO, or source content was mutated.

## Artifacts

- Ledger: `docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity-ledger.csv`
- Summary with source hashes: `docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity.summary.json`
- Empty fail-closed manifest: `docs/imports/rb-verified-oem-identities-wave233c-leoch-marathon-csb-2026-07-29.json`
- Builder: `scripts/build-rb-wave233c-leoch-marathon-csb-identity.py`
