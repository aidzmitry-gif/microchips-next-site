# Wave224-B: stageable manufacturer-primary materialization

The manifest contains exactly the 294 canonical Wave223-B candidates. Every product row copies manufacturer, model core, technology, technical attributes and source URL from the exact external-ID row in its SHA-pinned original source manifest. The only added provenance values are the strict source kind/tier, a publisher from the explicit URL/domain registry, model-core scopes and the date of the pinned source evidence.

The explicit registry covers 51 source URLs. It marks 216 official catalogues/datasheets and 78 official HTML product pages. It never infers a kind from a file extension. The stageable product contract has no claim text or fields outside Laravel's source-evidence allow-list.

No Laravel command or database access was run. The materialization contains no price, stock, media, publication, URL or identity mutation intent; it is a separately reviewed stage input only.
