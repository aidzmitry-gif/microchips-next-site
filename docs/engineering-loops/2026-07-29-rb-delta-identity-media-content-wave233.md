# Wave233 — Delta identity, exact media and manufacturer content

Date: 2026-07-29  
Site: `microchips-by`

## Result

- Profiled 611 published enrichment-queue products that still lacked a pinned identity but had a company-owned Bitrix preview image. The scope contains 553 UPS-battery cards, 57 primary-cell cards and one replacement-photo card; this wave did not expand the non-B2B categories.
- Three disjoint source reviews covered 389 UPS-battery cards:
  - Delta: 152 checked, 16 exact manufacturer-primary PASS, 136 HOLD;
  - Fiamm: 106 checked, 79 review-only candidates supported by an official distributor and 27 HOLD. The 79 were not applied because the identity command accepts manufacturer-primary evidence only;
  - Leoch, Marathon and CSB: 131 checked, 0 PASS and 131 HOLD because local exact SHA-pinned manufacturer evidence was absent, incomplete or conflicted.
- Applied only the 16 exact Delta identities. A repeat identity application returned `0 filled / 16 unchanged`.
- Exported 103 current company-owned legacy preview candidates after all prior review ledgers were excluded. Forty-seven shared-binary candidates were held before OCR. Of the 56 unique binaries, exactly 15 passed OCR and contact-sheet review; all 15 belong to the newly identified Delta set. `bitrix:2952 / DT 6033` remained HOLD because its expected model was not visible.
- Promoted the 15 exact Delta images and replaced all 16 legacy-only Delta descriptions with exact manufacturer-primary technical descriptions. No publication, price, stock, URL or indexability field changed.

## Verified database state

- 16/16 Delta products have manufacturer and exact MPN;
- 16/16 have an applied `official_manufacturer_product_page` description;
- 15 have verified exact media and one retains `legacy_exact_preview` media;
- 16/16 remain `availability=on_request`, 0/16 have a price.

## Readiness change

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Content-complete cards | 341 | 356 | +15 |
| Strict content ready | 162 | 177 | +15 |
| Queue to fixed 10% target | 1,301 | 1,286 | −15 |

The overall project readiness remains **60%**. This cycle improves catalog evidence but does not complete the remaining catalog, regional launch, infrastructure or post-launch gates.

## Verification

- Wave233 Python regression suite: 9 passed. The Fiamm test requires read-only Docker access; its isolated rerun passed 3/3.
- HTML prototype verifier: 4/4 passed.
- SEO audit with a process-local 512 MB PHP memory limit: 16,853 URLs, 97 redirects, 0 blockers.
- Commercial audit: 57 current price-evidence rows, 0 eligible 1C price rows, 0 mutations.
- Current readiness: 16,816 eligible published products, 356 content-complete, 177 strict-ready.

## Safety decisions

- Distributor evidence was retained for review but was not promoted to manufacturer-primary authority.
- Conflicting or duplicate normalized MPN/SKU values remained HOLD.
- Shared image binaries were not allowed to prove multiple products.
- One-way media/description apply commands rejected a second application after state transition; no duplicate writes were created.
- No commit or push was performed.
