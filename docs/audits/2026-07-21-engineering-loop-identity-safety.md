# Engineering loop: product identity safety

Date: 2026-07-21. Scope: RB shared-catalog import boundary. This loop does
not publish a product, amend 1C data, or change a public page.

## Outcome

The import boundary now rejects a product before publication when its
canonical `SKU` or `MPN` already belongs to another product. The same rule is
applied to 1C staging, cross-run publication and the Filament product form.

- `external_id`, `SKU` and `MPN` receive a canonical fingerprint: case,
  spacing and punctuation variants are treated as one identifier.
- PostgreSQL has unique normalized columns for each source identifier.
- Publisher transactions take PostgreSQL advisory locks for every canonical
  fingerprint, so two concurrent imports cannot both pass the same duplicate
  check.
- An incoming row with a known external ID cannot silently replace its stored
  SKU, MPN or manufacturer. It becomes `duplicate`, creates an open conflict,
  and remains unpublished.
- The product form requires a 1C ID and at least one commercial identifier;
  it does not allow those identity fields to be edited after creation.

The rule is intentionally conservative: `DT-12012` and `DT 12012` are not
merged; they are stopped for explicit review. A false positive therefore
cannot create a public duplicate or overwrite a product.

## Evidence

| Gate | Result |
| --- | --- |
| Backend regression | 155 tests, 535 assertions passed |
| New duplicate tests | staged punctuation variant, cross-run identity mutation, manual admin duplicate/change |
| Frontend lint | passed |
| Frontend unit tests | 9 files, 50 tests passed |
| Production Next.js build | passed |
| RB prototype gate | 4 of 4 prototypes passed |
| Working-tree whitespace check | passed |

## Data gate status

The latest read-only nomenclature audit retains the exact RB focus of 1,569
candidates and reports 93 review findings. It is evidence for review only,
not a publication list.

A fresh full extractor attempt did not replace the generated catalog evidence:
the extractor intentionally blocks output when it detects offer infoblocks
28/67 with active elements until their `CML2_LINK` relation is reconciled with
the parent catalog. This is a release blocker, not a failure to be bypassed.

The remaining organizational blocker is still source identity: provide a 1C
export or supplier price/MPN source for an initial reviewed batch (at least 50
RB focus products). Until then no automatic catalog transfer is allowed.

## Loop readiness

Four engineering gates are verified: source-safe staging, duplicate protection,
frontend regression and prototype regression. The source-reconciliation gate
is blocked, so this loop earns no catalog-publication readiness and does not
change country-launch progress. The next safe action is reconciliation of the
offer links and a human-reviewed 1C identity batch, not broader import work.
