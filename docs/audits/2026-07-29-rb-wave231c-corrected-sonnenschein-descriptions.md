# Wave231-C: corrected Sonnenschein source-backed description stage

A read-only DB check found both corrected identities (`S 12/17 G5`, `S 12/6.6 S`) but only `legacy_preview_applied` description drafts, not manufacturer-primary source-backed content. Wave230 had explicitly held `bitrix:3117` before its identity correction; therefore this is not a duplicate source-backed stage.

The manifest contains exactly the two corrected products. It reuses the SHA-pinned Exide Sonnenschein SOLAR catalogue and its pinned extraction; each corrected full MPN and its table row are rechecked. The titles retain `для ИБП` after the model, so strict exact display-name scope is unavailable; the stage uses bounded manufacturer-primary `model_core` evidence only.

This is a `--refresh-existing --refresh-applied` stage contract for replacing the two legacy-preview-applied drafts after review. The builder did not invoke Laravel, create an import run, apply a DB change, publish content, alter media, or change product identity.
