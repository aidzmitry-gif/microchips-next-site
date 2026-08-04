# Wave223-B: primary/rechargeable cells — source-backed candidates

Wave223-B uses exactly the 300 unique rows in the canonical Wave223-C B queue (`rb-enrichment-queue-wave223c-b-primary-rechargeable.csv`). That queue has already removed the 596 historical repeats and applied Wave220 IDs; this builder asserts the latter non-overlap again as a guard. The selected priority range is 631–930; it currently contains 300 primary-cell rows. Wave223-A cannot overlap because its declared categories are `seo:batteries-ups` and `seo:batteries-industrial`.

Before any content proposal, records are grouped by canonical manufacturer and normalized model core. 294 records have an exact external-ID match to a prior source-backed record, an official manufacturer host, a non-empty model core, and source-backed technical attributes. They form 81 manufacturer/model-core groups. The candidate manifest preserves the source URL and SHA-256 of the referenced prior evidence manifest.

The hold ledger contains 6 records: it retains products with no exact primary source or with evidence that cannot be grouped safely by a verified model core. No candidate is applied: this batch performs no database access and proposes no price, stock, identity, media, publication, or URL mutation.
