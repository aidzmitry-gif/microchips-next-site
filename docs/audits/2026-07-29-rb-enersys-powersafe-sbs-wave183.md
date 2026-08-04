# RB EnerSys PowerSafe SBS expansion — wave 183

Date: 2026-07-29. Site: `microchips-by`.

## Scope and primary evidence

The wave adds 32 exact EnerSys PowerSafe SBS identities that were absent after
normalized MPN and name checks:

- 21 PowerSafe SBS Top Terminal models;
- 11 PowerSafe SBS Front Terminal models.

Only primary manufacturer documents were used:

- Top Terminal range summary:
  `https://www.enersys.com/4aaf7f/globalassets/documents/product-documentation/powersafe/sbs/amer/Powersafe_SBS_Top_Terminal_Range_Summary_amer_en_rs_ps_sbs_tt_1022.pdf`
- Front Terminal range summary:
  `https://www.enersys.com/4a7a4d/globalassets/documents/product-documentation/powersafe/sbs/amer/en-rs-amer-ps-sbs-ft-0923.pdf`

The shared facts are limited to the documented TPPL/VRLA AGM technology,
construction, applications, temperature range, service-life statement and
standard. Voltage, C10 capacity, dimensions and typical mass are attached per
exact model from the corresponding manufacturer table. No model inherited a
neighbouring model's numeric values.

## Commercial and media boundary

- Availability is `on_request`; no stock quantity is asserted.
- Numeric price is null and no price-evidence row exists.
- `Offer` schema is absent.
- No image was copied because an explicit reusable-image licence was not
  established. The storefront uses the neutral placeholder.
- All product URLs remain `noindex` until the independent commercial and SEO
  promotion gate is satisfied.

## Reproducible artifacts

- `docs/imports/rb-manufacturer-series-enersys-wave183-source.json`
- `docs/imports/rb-manufacturer-product-candidates-enersys-wave183-2026-07-29.json`
- `docs/imports/rb-source-backed-description-drafts-enersys-wave183-2026-07-29.json`
- `docs/imports/rb-source-verified-preview-enersys-wave183-2026-07-29.json`

## Verification

- Candidate dry-run and apply: 32 createable/created, zero collisions.
- Description stage/apply and preview dry-run/apply: 32/32 accepted.
- `catalog:verify-manufacturer-preview-wave`: 32 products found, 32 distinct
  paths, zero price evidence, zero duplicate normalized MPN groups, passed.
- API `q=SBS 210F`: exactly one result, 12 V, 211 Ah, null price.
- API filter EnerSys + AGM + 2 V + 310 Ah: exactly SBS 300.
- Storefront SBS 210F: HTTP 200, exact model and facts, `noindex`, no `Offer`.
- Database boundary after the wave: 16,590 published RB market rows; 16,589
  canonical visible cards because one unrelated verified family variant is
  intentionally collapsed. The UPS category has 1,224 published rows and
  1,223 canonical visible cards.
- `seo:audit microchips-by --json`: PASS, 16,627 checked routes, seven
  redirects, zero blockers.

PHPUnit is not claimed: the production container excludes development
dependencies and the Windows PHP runtime lacks `mbstring`. Focused Python
generator tests passed 2/2; PHP syntax and runtime gates passed.
