# RB catalog readiness — wave 56

## Current local evidence

| Metric | Result | Interpretation |
| --- | ---: | --- |
| RB `site_products` | 7,295 | Every linked card has a 1C source; no external product row was added. |
| Public cards | 17 | Only the existing safe release slice is public. New work remains draft-only. |
| Uncategorised non-public cards | 414 | These need either a precise category/source match or must remain out of the release. |
| Applied source-backed descriptions | 40 | Product text is source-attributed before it can be released. |
| Pending source-image candidates | 4 | Remote assets are recorded without download, rights claim or public display. |

## Completed controls

- Exact normalised-name duplicate scan produced no draft duplicates.
- SKU and MPN duplicate scans produced no matching non-empty duplicate groups.
- The API provides allow-listed search and sorting; query variants are
  `noindex, follow` and retain the clean canonical category URL.
- `npm run build` uses Webpack explicitly after a Windows/Turbopack worker
  crash; the production build now completes.
- `npm run test` uses one Vitest worker because parallel forks are unstable in
  the current local Windows/Node runtime.
- The latest `seo:audit microchips-by --json` passed with zero blocking issues.

## Latest source-first enrichment

| 1C external ID | Confirmed model | Target category | Publication |
| --- | --- | --- | --- |
| `КА-00005622` | APC SURT192RMXLBP | UPS battery systems | Draft only |
| `ФР-00001952` | B.B. Battery BPS 26-12 | UPS battery systems | Draft only |
| `КА-00005359` | Inspired Energy PH3054HD29 | Rechargeable battery modules | Draft only |
| `КА-00001869` | XENOENERGY XL-050F/AX | Primary cells | Draft only |

## Next safe release rule

A card may move from draft to a public RB URL only when all of the following
are true: its 1C identity is stable, category is appropriate, technical text
has a recorded primary source, local commercial fields are confirmed, a
canonical URL and SEO record exist, and the release audit passes. A remote
image candidate never satisfies image readiness on its own.
