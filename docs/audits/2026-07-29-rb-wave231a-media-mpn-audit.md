# Wave231-A — audit of Sonnenschein media/MPN discrepancies

Checked: 2026-07-29. Scope is deliberately limited to three live product/media pairs. This is an audit only: no database, media, or import command was changed.

## Evidence chain

The live read-only query returned the current names, MPNs, media IDs, storage keys, hashes and `legacy_exact_preview` state recorded in the ledger. The local original files match those live media SHA-256 values.

The source registry pins two official Exide Technologies catalogues from `exidegroup.com`:

| Source | SHA-256 | Normalized-text check |
| --- | --- | --- |
| `exide-sonnenschein-a700.pdf` | `81ccc1905b0f257c0383ea6a9e24460873e41e74b152eaa6245a67e28b14cffa` | contains `A706105` and `A706140` |
| `exide-sonnenschein-solar-block.pdf` | `f065a4727d47d515d3bc9d8df09bbe4b8567ac53c7101806819287590ce80730` | contains `S1217G5` and `S1266S` |

All three local media originals were visually inspected. The detailed machine-readable ledger is `docs/audits/generated/rb-wave231a-media-mpn-audit.csv`.

## Findings and proposed actions

| Product | Classification | Evidence and action |
| --- | --- | --- |
| `bitrix:2808` / media `586` | Wrong image; MPN is correct | Product name and current MPN are `A706/140`, which is in the pinned A700 catalogue. The image label is visibly `A706/105`; that is a distinct model also present in the same catalogue. Preserve `A706/140`; detach or replace the image only after an approved `A706/140` image is identified. |
| `bitrix:2831` / media `607` | Truncated current MPN; image is correct | Name, image label, and pinned Solar catalogue identify `S 12/17 G5` / `S12/17G5`. Current MPN `S 12/17` omits the required `G5` suffix. Keep media and propose MPN `S 12/17 G5`. |
| `bitrix:3117` / media `834` | Truncated/incorrect current MPN; image is correct | Name, image label, and pinned Solar catalogue identify `S 12/6.6 S` / `S12/6.6S`. Current MPN `S 12/6` drops `.6 S`. Keep media and propose MPN `S 12/6.6 S`. |

No proposed action has been materialized. `bitrix:3117` should remain on the identity-correction hold until an explicitly approved MPN-correction stage is run.

## Follow-up manifest (Wave231-B)

The audit now has a deterministic, non-applying manifest at `docs/imports/rb-truncated-mpn-corrections-wave231b-2026-07-29.json`. It contains only `bitrix:2831` and `bitrix:3117`, with the current catalogue/media pins, a concise exact line from the SHA-pinned Solar catalogue, and the fields accepted by `catalog:correct-truncated-mpn`. Its accompanying UTF-8 extraction is hash-pinned in the manifest; the command requires that extraction and the SHA-pinned PDF to be copied beside the manifest in its execution directory. Generating these files does not invoke the command or change the database.

The manifest is serialized as ASCII-escaped UTF-8 JSON. This preserves the exact Cyrillic `current_name` values after JSON decoding while preventing host console code pages from rendering the file bytes as mojibake. The builder rejects a Wave231-A input name that differs from the two exact expected Unicode names or matches the Windows-1251/UTF-8 mojibake pattern.
