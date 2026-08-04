# Wave225-A preview-image review queue

The queue combines exactly 334 Wave224 source-evidence IDs (40 Wave224-A and 294 Wave224-B), joins the pinned Wave224 readiness snapshot and a read-only ProductMedia metadata export.

- 125 rows have a displayable preview and are explicitly `pending_human_review`; they are never auto-PASS.
- 209 rows lack a displayable preview and remain a media hold.
- The queue preserves Wave224 A/B evidence, external ID, manufacturer, bounded model core or MPN, and source provenance. Media metadata is evidence only; no asset is copied, promoted, published or applied.
