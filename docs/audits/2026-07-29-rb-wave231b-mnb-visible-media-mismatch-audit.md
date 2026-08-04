# Wave231-B: MNB visible-media mismatch audit

## Scope and method

This is a read-only audit of `bitrix:2909`, `bitrix:3056`, `bitrix:3099`, and `bitrix:3219`. The current PostgreSQL product and `product_media` fields were queried without an apply operation. Each original company-owned legacy asset was then visually inspected. Product identity evidence was compared to the existing SHA-pinned MNB official catalogue from Wave206:

- Snapshot: `docs/audits/sources/wave206-panasonic-ventura-mnb/mnb-official-catalogue.pdf`
- SHA-256: `85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859`
- Extracted text SHA-256: `c98577d15147e74b03ab645f1a926784d2dee2570e223a8a6c532b55b9e76372`

The full record-level evidence and proposed actions are in `docs/audits/generated/rb-wave231b-mnb-visible-media-mismatch-ledger.csv`.

## Findings

| Product | Current MPN / official catalogue | Visible label | Classification |
| --- | --- | --- | --- |
| `bitrix:2909` | `MNG 250-12` (GEL) | `MM250-12` | Wrong primary media |
| `bitrix:3056` | `MM 45-12` (AGM) | `MM55-12` | Wrong primary media |
| `bitrix:3099` | `MR 55-12FT` (AGM; catalogue typography is `MR 55-12 FT`) | `MR 80-12FT` | Wrong primary media |
| `bitrix:3219` | `MM 75-12` (AGM) | `MM55-12` | Wrong primary media |

For every row, the current product name, manufacturer, and MPN agree with the pinned official MNB catalogue. None should have its product identity changed from the image alone. The two observed alternative MM products are independently present in the current database: `bitrix:1574` is `MM 250-12` and `bitrix:3097` is `MM 55-12`. The official catalogue used here does not list `MR 80-12FT`; that absence makes the image unsuitable as identity evidence for `bitrix:3099`, not evidence against its source-backed `MR 55-12FT` identity.

All four current media records are still `legacy_exact_preview`, `primary`, and published. That status proves the original Bitrix element-to-file relation and rights basis, but its own verification note explicitly says that visual model identity requires review. This audit supplies that review and finds a visible mismatch in all four cases.

## Proposed action

Keep the product identity fields unchanged. For each row, after explicit authorization, either replace the primary asset with a company-owned image whose complete visible MPN matches the current MPN, or unpublish/remove the mismatched primary image until a replacement is available. Do not transfer these image files to the apparent peer products merely on visual similarity: their provenance is only the original Bitrix element relation. No database, media, publication, commercial, URL, or identity action was performed by this audit.
