# Pending Bitrix identity review — 50 rows

Read-only decision set for the first 50 pending candidates, deterministically ordered by candidate id. No candidate was promoted to `same_identity`: the pending queue’s snapshot/duplicate evidence is not first-party product proof and a duplicate-avoiding review must fail closed.

- Decisions: {"different_product_false_mapping": 2, "hold": 48}.
- Relation groups: {"not_in_duplicate_exact_review_queue": 50}.
- No row has the exact duplicate-evidence contract required by the Laravel review command, so no invalid or fabricated manifest was submitted. The other 50 rows are held as not eligible for that command because they are absent from the exact-review queue.
- No `--apply`, catalog, Product, SiteProduct, URL, SEO, media, publication, merge, or deletion mutation occurred.
- Capacity conflicts are marked `different_product_false_mapping`; all other exact-looking/ambiguous title relations are held for source-backed review.
