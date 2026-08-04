# Wave232-F: IPPON and EnerSys 12V70 exact-media review

Checked: 2026-07-29. This is an offline, deterministic review of four
company-owned Bitrix assets from Wave232 OCR batch 002. It does not run a
Laravel command or change database records.

## Result

| Target | Expected MPN | Local visual result | Official identity evidence | Verdict |
| --- | --- | --- | --- | --- |
| `bitrix:25120` | `Back Verso 800` | IPPON branding and chassis are visible; the complete model name is not legible. | [IPPON Back Verso 800](https://ippon.ru/catalog/item/ippon-800-751623/) and the official IPPON catalogue manifest prove the model identity only. | HOLD |
| `bitrix:25135` | `Back Basic 1500` | IPPON branding and chassis are visible; the complete model name is not legible. | [IPPON Back Basic 1500](https://ippon.ru/catalog/item/ippon-1500-1108030/) and the official IPPON catalogue manifest prove the model identity only. | HOLD |
| `bitrix:25149` | `Innova G2 2000L` | IPPON branding and chassis are visible; the complete model name is not legible. | [IPPON Innova G2 2000L](https://ippon.ru/catalog/item/ippon-2000L-1511522/) and the official IPPON catalogue manifest prove the model identity only. | HOLD |
| `bitrix:26048` | `12V70` | The complete `12V70` marking is visibly legible on the company-owned original. | [EnerSys PowerSafe V-TT datasheet](https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-tt/emea/en-v-rs-013.pdf), pinned locally, contains the exact `12V70` row. | PASS |

The three IPPON photos must not be promoted on visual resemblance: an official
catalogue/product page cannot substitute for a complete visible MPN on the
Microchips-owned asset. Their OCR results also remain HOLD. The EnerSys result
is a manual visual PASS despite an OCR HOLD because its printed label plainly
contains the complete exact MPN; the PDF corroborates identity only.

## Provenance pins

| Target | Media ID | SHA-256 | Storage path |
| --- | ---: | --- | --- |
| `bitrix:25120` | `1290` | `5ab86dd8a100dd837f99263a67a8f8c78e8b43c499d93e6f35e03f8ce187a043` | `legacy-staging/rb/bitrix-25120-84796.jpg` |
| `bitrix:25135` | `1302` | `b67ff6493471c7866099c6607885ec11328dd51ddbae17ee0ebd077bad5622ca` | `legacy-staging/rb/bitrix-25135-84826.webp` |
| `bitrix:25149` | `1315` | `a0b761b94b3cee8bc903df54699f1c5386e6718fce73dd34001ef33c8ab210de` | `legacy-staging/rb/bitrix-25149-84854.jpg` |
| `bitrix:26048` | `1566` | `02262855e7028579f920495192eba0ec4bdfc791a3248be5ff4b2434ef2f31a5` | `legacy-staging/rb/bitrix-26048-90293.webp` |

All four assets retain the same rights basis: `Company-owned Microchips legacy
Bitrix upload backup.` No official IPPON or EnerSys image was downloaded,
stored, referenced as a publishable asset, or used as a rights basis.

## Deterministic artifacts

`scripts/build-rb-wave232f-ippon-enersys-media-review.py` SHA-pins the
Wave232 OCR input/review/ledger, company-owned source export, three IPPON
identity records, the EnerSys identity record and its local manufacturer PDF.
It re-hashes every local image before producing:

- `docs/audits/generated/rb-wave232f-ippon-enersys-media-review.csv` — four
  review outcomes, including all HOLD rows;
- `docs/imports/rb-legacy-exact-preview-media-wave232f-2026-07-29.json` — the
  sole eligible `12V70` promotion row; and
- `docs/audits/generated/rb-wave232f-ippon-enersys-media-review.summary.json`.

The manifest uses the existing `PromoteLegacyExactPreviewMedia` schema and
contains no source image URL, price, commercial data, or publication field. It
is an execution candidate only: no dry-run or `--apply` command was invoked.
