# Wave208-D — read-only Motorola duplicate survivor plan

## Scope

Wave208-D audited the nine strict manufacturer+model groups found in Wave207:

- seven two-card groups;
- one three-card group (`HNN9008A`);
- one four-card group (`HNN9628A`);
- 21 current RB product cards in total.

The audit was read-only. No product was merged, removed, redirected or otherwise changed.

## Commercial and content state

| Dimension | Result |
|---|---:|
| Current prices | 0 |
| Current price-evidence rows | 0 |
| Current `in_stock` states | 0 |
| Offer schemas | 0 |
| Legacy Bitrix price claims | 21 |
| Legacy Bitrix `IN_STOCK=Y` claims | 21 |
| Product media / verified media | 0 / 0 |
| Applied legacy-preview descriptions | 21 |
| RB site URLs / SEO rows | 21 / 21 |
| Indexable SEO rows | 0 |
| Existing matching redirects | 0 |
| Confirmed 1C links | 0 |

All current cards remain honest `on_request` noindex previews. The old Bitrix prices and stock flags are retained as audit evidence only and do not authorize current price, stock or Offer output.

Each member has its own applied legacy-preview description and its own URL/canonical pair. Description fingerprints differ inside every group because the titles and compatible-radio claims differ.

## Survivor decision

Safe survivor groups: **0 / 9**.

No survivor was selected. A shared Motorola replacement token is not sufficient proof that differently named legacy packs are the same sellable product. Wave207 has no pinned primary Motorola battery snapshot for these groups, while collapsing now would discard distinct compatibility/title content and one of the existing preview URLs unless the information were first merged and revalidated.

Before any future collapse, each group requires:

1. an exact primary Motorola battery source tied to the offered part;
2. a merged and verified compatibility set;
3. a repeated commercial, media, description, URL/redirect and 1C loss audit.

## Artifacts and verification

- `docs/audits/generated/wave208-motorola-duplicate-db-snapshot.json`
- `docs/audits/generated/wave208-motorola-duplicate-survivor-plan.csv`
- `docs/audits/generated/wave208-motorola-duplicate-survivor-plan-summary.json`
- `scripts/build-rb-wave208-motorola-duplicate-survivor-plan.py`
- `scripts/tests/test_wave208_motorola_duplicate_survivor_plan.py`

Verification:

- live Laravel/PostgreSQL read-only snapshot: 21 / 21 products;
- deterministic snapshot replay: passed;
- Wave208-D tests: 6 passed;
- automatic collapses / database mutations: 0 / 0.
