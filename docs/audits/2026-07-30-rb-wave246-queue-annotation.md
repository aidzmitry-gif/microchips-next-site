# Wave246 queue consolidation

Annotated queue: 1,236 unique rows. Wave245 intersection: 1,236; added: 0; removed: 11. All removed rows are exactly the 11 reviewed-media visual PASS products, so they are recorded as retired rather than falsely re-added or marked inside the queue.

All 276 frozen decisions are accounted: A 92 media holds/no-safe-mutation, B 88 dry-run-ready-not-applied plus 4 exact-owner holds, C 56 prior-reviewed no-repeat noops plus 36 media holds. No status claims apply where the ledger reports noop or dry-run only.

Five reviewed-media HOLD rows remain in the queue and are marked `wave246_media_visual_hold`. Research statuses from Wave245 are carried for every non-overridden intersection row.

Verification: exact queue cardinality 1,236; unique IDs; membership delta −11/+0; scope accounting 276/276; promoted-media retired 11/11. No DB/apply/commit/push.
