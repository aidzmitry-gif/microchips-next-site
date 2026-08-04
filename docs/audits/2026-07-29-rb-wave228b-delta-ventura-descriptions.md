# Wave228-B: Delta and Ventura exact-source description refresh

Wave228-B selects only the 13 Wave227 rows that have a verified published image, no applied description, and manufacturer Delta (8) or Ventura (5). Every staged row has exact MPN scope and manufacturer-primary evidence. Delta facts are copied from the hash-pinned Wave206/Wave211B official product-page evidence and then rechecked against the pinned HTML snapshot. Ventura facts are read from the hash-pinned official 2023 catalogue PDF/text snapshot.

The manifest is a stage-only refresh contract for existing legacy-preview drafts: `--refresh-existing --refresh-applied`. It does not run an importer or make a database change. Products without their exact MPN in the pinned official source are written to the HOLD ledger and excluded from the manifest.

The Ventura GP 12-40 and GP 6-9 catalogue rows expose 42 Ah and 8.7 Ah respectively; these official values are retained rather than inferring the legacy title's rounded capacity. HR 1228W and HR 1234W are represented with the catalogue's 15-minute watt/block rating, not an inferred Ah rating.
