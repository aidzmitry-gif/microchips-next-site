# Wave243C — remaining Leoch/APC/CSB/Marathon/EnerSys descriptions

Date: 2026-07-29  
Market: Belarus (`microchips.by`)  
Mode: evidence and Laravel dry-run only; no apply, commit, or push

## Scope and no-repeat result

The frozen Wave242 queue contains 108 missing verified descriptions in this lane: Leoch 50, APC 22, CSB 16, Marathon 8, and EnerSys 12. Wave233C, Wave234B, Wave242, and the APC Wave199 collision ledger are SHA-pinned inputs. Their URLs and snapshots were not researched again.

The partition is deliberately fail-closed:

- **1 PASS**: `bitrix:23844`, offered as APC `RBC109`. A newly archived Schneider Electric datasheet identifies `APCRBC109` / cartridge 109 and states sealed lead-acid construction, two battery blocks per string, and `Battery Volt-Amp-Hour Capacity 9`.
- **107 HOLD**: prior suffix, capacity, collision, compatibility, or absent-exact-source findings remain unchanged. Search-only pages that could not be archived with a local SHA were not admitted as evidence.

The new official PDF is `docs/audits/sources/wave243c-apc/apcrbc109.pdf`, SHA-256 `0490bc1d939ec5f00df80b5c595f0161811b9fdf2f00387e11fe2f6e2db7871a`, from `https://iportal.se.com/Contents/docs/UPS-APCRBC109_Data%20sheet.pdf`.

## Exact legacy duplicates found first

Four APC Bitrix rows are already exact normalized-MPN duplicates of canonical 1C products and remain HOLD; no exclusion was applied:

| Legacy row | Model | Canonical survivor |
|---|---|---|
| `bitrix:20088` | `RBC7` | `КА-00003292` |
| `bitrix:23799` | `RBC23` | `КА-00005164` |
| `bitrix:23811` | `RBC31` | `КА-00003200` |
| `bitrix:23818` | `APCRBC141` | `КА-00003237` |

## Laravel dry-run

The manifests were copied only to the backend container's `/tmp` directory so their relative SHA-pinned snapshot could be validated.

- `catalog:apply-verified-oem-identities` without `--apply`: accepted 1 record, `identities_filled=0`, commercial changes 0, publication changes 0. The live row remains manufacturer/MPN-null because dry-run does not persist prerequisites.
- `content:stage-source-backed-description-drafts` without `--apply`: `0 created, 0 refreshed, 1 unchanged`; none published.
- A subsequent description-application dry-run correctly stopped with `no applicable source-backed editorial draft`, because the preceding identity dry-run was rolled back. No sequential state was persisted.

The host PHP fallback could not run database validation because its SQLite PDO driver is absent; the healthy Docker Laravel/PostgreSQL contour was used instead.

## Outputs

- `docs/audits/generated/rb-wave243c-remaining-description-ledger.csv`
- `docs/audits/generated/rb-wave243c-remaining-description.summary.json`
- `docs/audits/generated/rb-wave243c-exact-legacy-duplicates.csv`
- `docs/imports/rb-verified-oem-identities-wave243c-2026-07-29.json`
- `docs/imports/rb-source-backed-descriptions-wave243c-2026-07-29.json`

No prices, availability, publication state, URLs, images, or database schema were changed.
