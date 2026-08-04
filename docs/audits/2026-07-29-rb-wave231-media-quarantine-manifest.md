# Wave231: media identity-mismatch quarantine manifest

This deterministic manifest combines the two Wave231 audit ledgers, the frozen Wave227 media export, and a read-only current DB product/site-product/media snapshot. It pins exactly seven currently published `legacy_exact_preview` assets with company-owned rights.

Five entries have visible labels for a different product and use `quarantine_wrong_product_media`: `bitrix:2808`, `bitrix:2909`, `bitrix:3056`, `bitrix:3099`, and `bitrix:3219`. Two entries have a visibly more specific identity than the current, truncated MPN and use `hold_truncated_identity_preview`: `bitrix:2831` and `bitrix:3117`. The builder proves for both holds that the normalized observed MPN strictly extends the current MPN and that it is present in the current product name.

Every row now carries the reviewer and a SHA-256-pinned audit-ledger basename. `QuarantineIdentityMismatchMedia` resolves review evidence beside the manifest at runtime. Therefore a Docker dry-run must copy the JSON manifest and the two source ledgers `rb-wave231a-media-mpn-audit.csv` and `rb-wave231b-mnb-visible-media-mismatch-ledger.csv` into the same container directory, retaining their exact basenames and bytes. This builder did not invoke the command, create an import run, apply any DB/media state, or publish changes.
