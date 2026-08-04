# Wave213-C: five unresolved industrial-cell rows

Wave213-C is exactly the five `unresolved_industrial_cell` records in the
Wave212 source batch: `bitrix:11348`, `bitrix:11349`, `bitrix:11351`,
`bitrix:11426`, and `bitrix:1688`.  All stay `no_evidence` and none enters an
OEM-identity manifest.

The Wave213 selectors are a disjoint 500-row union: A is 274
`unresolved_replacement` rows, B is 221 `unresolved_other` rows in
`seo:power-systems`, and C is these five industrial-cell rows. C has no
intersection with the 2,000-row processed register; automotive and electronics
scope counts are both zero.

The titles preserve the available designations: Flight 60 Internal
`V60-19100-63`; Flight 60 Main `V60-19000-63`; Fluke Biomedical INCU II
Incubator (the title's `10200mAh` is not an MPN); Marco KM500 (Nidek)
`MA-3010`; and ZAIT `НК-80` without electrolyte.  Each needs a first-party
accessory/service or catalogue source before a manufacturer-plus-MPN claim.

The official Fluke Biomedical INCU II page confirms the device, but does not
identify a replacement battery; it is therefore evidence of the device only,
not an importable battery identity.  The local 1C matching file contains an
inventory-name match for ZAIT НК-80, but this too is not manufacturer-primary
evidence.

Duplicate checks use the full canonical registry and a read-only live database
query.  The Laravel command was invoked without `--apply` against the empty
exact-safe manifest. It rejected it, as designed, because the command requires
a non-empty product list; no database mutation occurred. See the generated
evidence CSV, live collision receipt, dry-run receipt and summary.
