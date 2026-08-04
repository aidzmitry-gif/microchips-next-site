# Wave219-C Robiton adapter taxonomy follow-up

One explicit AC/DC adapter is corrected from the chargers leaf to the existing power-supplies leaf. This is a category-only dry-run receipt; no identity field is included in the manifest.

## Strict move manifest

| Product | From | To |
| --- | --- | --- |
| `КА-00002676` — Адаптер/блок питания ROBITON B9-500 5,5x2, 1/12 | `seo:chargers` | `seo:power-supplies` |

The CSV has exactly the required three columns and one row. It uses existing `full_catalog_seo_tree` categories only.

## Explicit exclusion

`ФР-00001523` is deliberately absent: it is already in `seo:power-supplies`; live identity remains manufacturer `Phoenix Contact` and MPN `2938646`. Its Wave219-C manufacturer-cluster finding is not a taxonomy instruction.

## Laravel dry-run

- Exit: 0; validation errors: 0; rows: 1.
- `--apply` was not passed. The command transaction rolled back; category links, URLs, canonical paths, publication and identity fields were unchanged.

## Verified application

- ImportRun 954 moved the single noindex route; publication fields changed: 0.
- ImportRun 955 proved idempotence with one already moved.
- Post-apply SEO audit: 16,853 URLs, 97 redirects, 0 blockers.
- Receipt: `docs/audits/generated/wave219c-robiton-category-application-receipt.json`.
