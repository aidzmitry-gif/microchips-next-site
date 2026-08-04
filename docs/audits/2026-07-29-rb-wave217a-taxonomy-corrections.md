# Wave217-A conservative taxonomy corrections

This candidate manifest moves only product types whose title and Wave217-A factual classification state an unambiguous existing target leaf.
Tool battery-plus-charger kits remain in `seo:replacement-tools`: a bundle has two buyer intents, so it is intentionally not auto-moved. Warehouse equipment and traction batteries already match their categories and are also untouched.

## Candidate moves

- Total: 91
- Targets: {'seo:power-converters': 26, 'seo:power-supplies': 53, 'seo:ups-systems': 12}
- Categories used: existing `full_catalog_seo_tree` leaves only; no taxonomy node is created.
- No automotive or electronic-component row is present.

## Dry-run

- Laravel category mover exit: 0; validation errors: 0.
- `--apply` was not passed. Category links, URLs, canonical paths, publication fields and product identity remain unchanged.

## Verified application

- ImportRun 941 moved 91 category links and their 91 noindex routes; publication flags changed: 0.
- ImportRun 942 proved idempotence: 0 moves, 91 already moved.
- Post-apply SEO audit: 16,853 URLs, 97 redirects, 0 blockers.
- Receipt: `docs/audits/generated/wave217a-category-correction-application-receipt.json`.
