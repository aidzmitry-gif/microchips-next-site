# RB catalogue scope cleanup — 2026-07-26

## Evidence-led exclusion

The 1C export contained a mixed operational inventory, not only the
microchips.by customer catalogue. The unclassified queue was inspected by
explicit title signals only:

- food: 253;
- office goods: 374;
- household goods: 224;
- services, finance and fuel: 24.

Total explicit out-of-scope rows: **875**. They were validated first and then
removed only from the unpublished `microchips-by` site-product relation.

## Result

- RB non-public product drafts after scope cleanup: **8,209**.
- RB public products: **0**.
- Shared canonical products preserved: **9,084**.
- Other market profiles were not altered.

The remaining technical research queue contains **2,214** rows. It is not an
SEO publish list and is reserved for additional technical classification,
manufacturer-source research and media verification.

## Follow-up exclusion and strict duplicate gate — 2026-07-27

The second scope pass found 243 additional explicitly non-profile records
(food, household, office, automotive and service titles) among the remaining
drafts. It was first run in validation mode, then applied only after the
command confirmed that every record was unpublished.

The strict normalized-name duplicate register was then processed in the same
two-step mode. It contained 155 duplicate site listings. The command removes
only the RB `site_products` relation, retains the chosen canonical survivor,
and cannot operate on a published item.

Post-apply database evidence:

- RB non-public product drafts: **7,811**;
- RB public products: **0**;
- open duplicate conflicts: **0**;
- shared canonical products and other market profiles: unchanged.

This is catalogue hygiene, not publication approval. Every remaining draft
still requires category, source-data and commercial-data gates before it can
be visible to search engines or customers.

## Live unclassified-sample correction — 2026-07-27

A direct sample of live no-category drafts found additional explicit office,
household and apparel items that were not covered by the initial narrow
vocabulary. The scope triage now accepts both `external_id` and
`product_external_id` exclusion manifests, preventing a non-empty exclusion
file from being treated as empty on a repeat run.

The expanded vocabulary identified 169 candidates. It was intersected with
the live RB unpublished-product export first: 129 were still linked to the
market, while the rest had already been excluded or deduplicated. The exact
129-record delta passed the draft-only validation command before apply.

Post-apply database evidence:

- RB non-public product drafts: **7,682**;
- exactly one `full_catalog_seo_tree` leaf: **5,868**;
- no target leaf yet: **1,814**;
- multiple target leaves: **0**.

The 1,814 no-leaf records remain a research queue. They are not assigned to a
generic category merely to improve a percentage.

## Second live-sample correction — 2026-07-27

The next live sample exposed a further 41 records whose wording is explicit:
document filing/stationery, workwear and leisure goods, or named automotive
repair parts. The vocabulary deliberately uses narrow phrases; battery
holders, power converters, cell packs and other technical wording remain in
the research queue.

All 41 records passed the same non-public-only validation before the site
links were removed.

Post-apply database evidence:

- RB non-public product drafts: **7,641**;
- exactly one `full_catalog_seo_tree` leaf: **5,868**;
- no target leaf yet: **1,773**;
- multiple target leaves: **0**.
