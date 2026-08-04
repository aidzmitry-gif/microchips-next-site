# Wave231-C — exact legacy preview media promotion manifest

Checked: 2026-07-29. This is a deterministic manifest only; it does not run the Laravel command and does not change media or product records.

## Scope

| Product | Corrected MPN | Media pin | Visual evidence |
| --- | --- | --- | --- |
| `bitrix:2831` | `S 12/17 G5` | `607`, `97f2f74e7bf600ef4fbeb9d9716d5133957ea283cd656b8a7294069fb90882d9` | Wave231-A original visibly labels `S12/17 G5`. |
| `bitrix:3117` | `S 12/6.6 S` | `834`, `d55a893ff54034b9a2cebc3827e57ea4c862b5dccd5ac3a7edfe1b6bf8bf713c` | Wave231-A original visibly labels `S12/6.6 S`. |

Both rows are exact-MPN promotions: the manifest uses `identity_scope: exact` and `identity_evidence_level: visible_exact_mpn`, never a model-core fallback. It pins the published legacy preview storage path, SHA-256, and `Company-owned Microchips legacy Bitrix upload backup.` rights basis required by `PromoteLegacyExactPreviewMedia`.

The manifest is `docs/imports/rb-legacy-exact-preview-media-wave231c-2026-07-29.json`. At execution, the command independently requires the current product MPN, published site product, legacy preview status, media ownership, path, rights, and stored-asset SHA to remain unchanged. No command invocation was performed for this wave.
