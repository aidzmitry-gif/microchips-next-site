# Wave230-B: MNB and EnerSys frozen description stage

Wave230-B uses exactly the frozen 25-row slice: MNB 13 and EnerSys 12. It reuses only SHA-pinned manufacturer-primary registries and snapshots already acquired in Wave206, Wave209A and Wave215C; no new source research was performed. Every target is cross-checked against the Wave229 reviewed-media manifest by external ID, media ID, media SHA-256, exact visible-MPN evidence, and company-owned rights basis.

All 25 current names contain a technical suffix after their model token. The strict `nameEndsWith MPN` condition is therefore false for every row, so the manifest uses bounded `model_core` evidence only; it makes no exact-MPN display-name claim. MNB catalogue OCR is normalized only for the Cyrillic `М` glyph in the `MM 33-12` table cell, while preserving the same hash-pinned catalogue source. The two Cyclon Cell titles reuse the prior source-proven series-to-catalogue-part mapping from Wave215C.

This is a stage-only `--refresh-existing --refresh-applied` contract. The builder did not run an importer, DB apply, publication, media, commercial, URL, or identity change.
