# RB explicit battery services exclusion wave 88 — 2026-07-28

## Result

- Excluded 36 explicit service records from the unpublished `microchips-by` site scope.
- The bounded set contains only action records whose 1C names state repair, diagnostics, charging, disassembly/assembly, battery-set or control-board replacement, or contact welding.
- Preserved all 36 canonical products and all 36 non-group 1C inventory records; only RB `site_products` links were removed.
- Other markets and published records were not changed.
- `seo:electronic-components` was not touched.

## Adversarial review

- The service-keyword scan returned 53 unpublished non-electronic RB rows.
- Accepted 36 rows where the product name itself is an explicit service action.
- Rejected 17 false or ambiguous hits, including real batteries stored under a 1C `Услуги` folder, an UPS whose name mentions rack installation, a mounting knife, cable ties, a warehouse trolley, a socket and product battery blocks.
- No finance or automotive-only row was added without equally explicit 1C evidence.

## Safety gates

- Manifest: 36 rows and 36 unique product IDs.
- Pre-apply guard: 36/36 canonical products, RB links and non-group 1C items existed; 36/36 RB links were unpublished; 0 had electronic-components links.
- Dry-run import `455`: 36 non-public RB drafts validated; 0 canonical products deleted; 0 published products changed.
- Apply import `456`: 36 RB drafts excluded; 0 canonical products deleted; 0 published products changed.
- Post-apply guard: 0/36 RB links remained, while 36/36 canonical products and 36/36 1C records still existed.
- Replay dry-run import `458` was blocked with `products are not linked to this site`, proving the strict exclusion command cannot apply the same removal twice.
- `seo:audit microchips-by --json`: PASS, 42 URLs checked, 0 blocking issues.

## Reproducible manifest

- `docs/imports/rb-scope-exclusion-wave-88-explicit-battery-services.csv`

`catalog:exclude-site-drafts` remains dry-run unless `--apply` is supplied and never deletes canonical products.
