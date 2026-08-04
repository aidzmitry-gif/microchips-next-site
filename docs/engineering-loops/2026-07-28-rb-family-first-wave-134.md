# RB family-first catalogue — Wave 134 (superseded 2026-07-28)

## Status

**SUPERSEDED / NOT VALID CURRENT EVIDENCE.**

The initial GP1272 pilot incorrectly treated `КА-00001364` and
`КА-00001276` as different terminal variants. The raw 1C identities show that
both are the same `CSB GP1272 F2` execution; `ФР-00001807` is a third country-
wording duplicate. Country/warehouse wording is not a product variant.

The error was caught while all product pages were still `noindex`. Wave 134
received no strict-completeness credit and created no indexable URL.

## Correction

- The replayable false-family manifest and the duplicate-target description
  manifest were removed from `docs/imports/`.
- `КА-00001276` was collapsed into survivor `КА-00001364`; only the RB
  `SiteProduct` and false `ProductVariant` relation were deleted. The shared
  product identity was retained for audit and other-market safety.
- The empty GP1272 family was deleted.
- The survivor was refreshed against the current CSB base GP1272 catalogue.
  Facts specific to the separate 12V25W/12V28W executions were removed.
- Current evidence and replacement verification are recorded in Wave 135.

Do not use the former Wave 134 runtime/API/browser claims as current evidence.
