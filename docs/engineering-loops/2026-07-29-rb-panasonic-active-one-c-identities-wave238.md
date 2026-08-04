# RB Panasonic active-1C identities — Wave238

Date: `2026-07-29`  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

Wave238 closes three exact Panasonic identity gaps on already-active 1C
products. It does not create products and does not repeat the 57 package and
terminal variants reviewed in Wave200.

- `КА-00003142` → `Panasonic BR2032`;
- `ФР-00000639` → `Panasonic CR2012`;
- `ФР-00001236` → `Panasonic CR2450`.

All three models occur exactly once as bounded tokens on their pinned pages in
Panasonic Energy's official coin-cell catalogue. The PDF SHA-256 is
`1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343`.
No current normalized MPN or SKU collision exists for any target.

## Fail-closed active-1C path

`catalog:apply-verified-oem-identities` now has an explicit `active_1c` target
kind. It is deliberately narrower than a general importer:

1. only non-Bitrix external IDs with `status=active` are accepted;
2. the current title must still contain manufacturer and exact MPN candidate;
3. manufacturer/MPN can only fill blank fields;
4. global normalized MPN/SKU collision checks remain mandatory;
5. every affected page must be published but `noindex`, with no Offer schema;
6. SHA-pinned HTTPS manufacturer evidence is required;
7. price, availability, publication and SEO schema fields cannot change.

The first dry-run correctly rejected an over-wide manifest row. The builder
was tightened so page/excerpt proof remains in the audit ledger while the
runtime manifest contains only the command's allowlisted fields. The corrected
dry-run then accepted all three records.

## Application evidence

- Manifest: `docs/imports/rb-verified-oem-identities-wave238-panasonic-active-1c-2026-07-29.json`;
- Manifest SHA-256: `ec49710688a698764199292b40cfebc3492f1ba2b19f1918b627e3c0bfee36e1`;
- dry-run: 3 accepted, zero mutations;
- apply: 3 identities filled;
- idempotence rerun: 0 filled, 3 unchanged;
- completed import run: `1027`;
- database check: all three products are active, published, noindex,
  `on_request`, unpriced and have null Offer schema.

No price, stock, name, technical attribute, media, URL, publication or SEO
field changed. Global commercial state remains 57 priced rows and 24,348
`on_request` rows across all site profiles (24,298 for `microchips-by`).

## Readiness and SEO

- eligible published RB products: 16,816;
- content-complete cards: 392 (unchanged);
- strict-content-ready cards: 213 (unchanged);
- remaining 10% enrichment queue: 1,250 (unchanged);
- Panasonic rows with blank MPN inside that queue: 63 → 60;
- SEO release audit: 16,853 URLs, 97 redirects, 0 blockers;
- RB prototype gate: 4 of 4 passed.

Identity is a separate quality gate, so this evidence improvement does not
claim a content-completeness increase or a project percentage increase.

## Verification

- deterministic Python builder tests: **2 passed**;
- Laravel identity workflow: **9 tests, 68 assertions**;
- runtime dry-run, apply, database verification and idempotence passed;
- regenerated Wave238 enrichment queue and full readiness audit;
- no commit or push was performed.

## Next step

Continue from the no-repeat Wave238 queue with the largest intersection of
manufacturer-primary descriptions and verified exact media. The three remaining
Panasonic active-1C holds (`BK-3MCCE`, `NCR18650GA`, `VL2020`) stay on hold until
local SHA-pinned primary snapshots are available.
