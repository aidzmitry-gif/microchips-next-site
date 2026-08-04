# Wave228-C: strict B.B. Battery, Casil and EnerSys Cyclon description refresh

The Wave227 readiness snapshot contains 52 image-verified products without an applied description. This frozen slice contains exactly 11: four B.B. Battery, five Casil and two EnerSys Cyclon products.

- Every candidate has an exact source MPN token, HTTPS first-party URL, SHA-256-pinned local snapshot and a conservative technology-only attribute.
- B.B. Battery uses existing manufacturer series snapshots; Casil uses existing exact manufacturer product-page snapshots; EnerSys Cyclon uses the existing official selection-guide snapshot.
- The stage manifest deliberately omits snapshot fields because the Laravel source-evidence contract rejects them; the companion ledger retains each path and hash.
- The DB catalogue names retain technical suffixes after the exact model token, so the Laravel exact-MPN end-of-name rule rejects them. The stage contract therefore uses bounded manufacturer-primary `model_core` evidence, not an exact MPN or display-name claim. All 11 currently have `legacy_preview_applied` drafts. This is a strict source upgrade candidate for `--refresh-existing --refresh-applied`; this builder did not run that command, apply a database change, publish content, or alter commercial/media data.
