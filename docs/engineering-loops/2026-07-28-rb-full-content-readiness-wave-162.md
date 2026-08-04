# RB full-catalog content readiness — wave 162

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 162 classified all 16,415 published RB products, extracted the complete
Bitrix content snapshot, and attached the first bounded batch of exact legacy
descriptions to the same noindex product records.

| Metric | Result |
| --- | ---: |
| Published RB products | 16,415 |
| Full Bitrix catalog records | 21,132 |
| Bitrix records with preview text | 1,726 |
| Bitrix records with detail text | 20,992 |
| Exact descriptions attached in this wave | 1,000 |
| Exact legacy descriptions after the wave | 2,465 |
| Eligible descriptions remaining | 13,588 |
| Revalidation batches | 11 |
| Published products with a price | 34 |
| Indexable product URLs | 0 |
| Safe local media coverage | 13,132 / 16,415 (80.0000%) |

The source CSV has SHA-256
`43bcd6efe4e9b809f007b85160dd876e5aecdf471fec44faf460b012ece71517`.
The importer requires this digest, the exact 21,132-row count, a completed
`bitrix_full_catalog_snapshot` run, and an exact `bitrix:<id>` plus normalized
name match.

## Readiness registry after the batch

| Readiness class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 2,334 |
| `legacy_text_only` | 131 |
| `legacy_preview_only` | 10,710 |
| `thin_unidentified` | 2,998 |

There are now 2,707 cards with some classified text evidence, but this is not
equivalent to SEO readiness. Only manufacturer-backed, identity-safe content
may later pass the strict publication gate.

## Full-catalog triage

The deterministic triage of the 16,327 non-complete cards produced:

- 14,419 `hold_missing_identity` records;
- 1,842 identity candidates needing a primary source;
- 66 identity-present research-cluster records;
- 1,361 unique research clusters;
- 363 duplicate-candidate pairs, all retained as variant/fact-conflict holds.

No duplicate, identity, price, stock, warranty or indexability decision was
automatically inferred from descriptive text.

## Verification

- importer dry-run before apply: 14,588 eligible, 1,000 selected;
- apply: exactly 1,000 descriptions created, 11 revalidation batches;
- importer dry-run after apply: exactly 13,588 eligible remain;
- PostgreSQL: 2,465 exact legacy drafts, 16,415 published products, 34 priced
  products and zero indexable product URLs;
- PHPUnit: 4 tests, 41 assertions passed;
- browser: `legacy-bitrix-2388` rendered the sanitized description and
  `/api/media/5011` at natural width 656 px;
- browser: the same card retained `noindex, nofollow` and request-price state;
- a newly described no-image card also rendered its text without inventing an
  image.

## Safety boundary

Legacy Bitrix text is company-owned migration material and is useful for
preview completeness, but it is not treated as manufacturer verification.
The importer strips markup and executable content, limits description length,
does not overwrite existing descriptions, and leaves price, availability,
canonical identity and indexability unchanged.

## Next step

Continue the remaining 13,588 exact-description queue in bounded batches while
running duplicate and source-quality research as a separate gate. Prioritize
the 2,998 `thin_unidentified` records for identity recovery and keep all such
pages noindex until strict evidence is complete.
