# RB full-catalog content readiness — wave 164

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 164 attached 1,700 additional exact Bitrix descriptions in command-bounded
sub-waves of 1,000 and 700. Two independent read-only audits then reviewed the
remaining thin-page and duplicate risk instead of treating legacy text as SEO
publication evidence.

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Cards with classified text evidence | 4,407 | 6,107 | +1,700 |
| Text-evidence coverage | 26.85% | 37.20% | +10.36 pp |
| Exact legacy description drafts | 4,165 | 5,865 | +1,700 |
| Eligible exact descriptions remaining | 11,888 | 10,188 | -1,700 |
| Published RB products | 16,415 | 16,415 | 0 |
| Published products with a price | 34 | 34 | 0 |
| Indexable product URLs | 0 | 0 | 0 |

Safe local media coverage remains 13,132 / 16,415 (80.0000%).

## Readiness registry after the batch

| Readiness class | Products |
| --- | ---: |
| `strict_content_ready` | 34 |
| `source_backed_partial` | 208 |
| `legacy_content_preview` | 5,503 |
| `legacy_text_only` | 362 |
| `legacy_preview_only` | 7,541 |
| `thin_unidentified` | 2,767 |

The 6,107-card total is a migration-completeness metric, not strict SEO
readiness. Legacy text remains non-manufacturer evidence and every migrated
product page remains noindex.

## Thin-page priority audit

The current 2,767 `thin_unidentified` records are concentrated in four
categories:

| Category | Products |
| --- | ---: |
| Laptop replacement batteries | 2,188 |
| Industrial batteries | 488 |
| Transport replacement batteries | 89 |
| Mobile replacement batteries | 2 |

All have no stable identifier, manufacturer field, SKU/MPN, technical facts or
displayable image in the readiness registry. The pre-wave audit found the
laptop title queue dominated by Lenovo, HP, ASUS and Dell markers, but brand
membership alone cannot prove compatibility or technical facts. Repeated
apparent part numbers also contain capacity, voltage, OEM and package variants,
so they must not be merged by title token alone.

The next safe mass action for this cohort is staged identity normalization:
extract apparent P/N and title-stated facts as unverified candidates, then
research only exact model clusters against primary sources.

## Duplicate audit

- database: 25,970 Products and 25,970 distinct external IDs;
- 5,865 exact legacy description drafts belong to 5,865 distinct Products;
- zero Products have more than one exact legacy description draft;
- current duplicate register: 363 pairs, 187 clusters, 550 Products;
- every pair remains `variant_or_fact_conflict_hold`; safe automatic merge or
  exclusion candidates: zero.

The description command has no Product, SiteProduct or URL creation path. A
separate immutable-field manifest is required for the 550 duplicate
participants; a merge may be authorized only when manufacturer, MPN, voltage,
capacity, technology and variant/terminal/package fields all agree.

## Verification

- first dry-run/apply: exactly 1,000 descriptions, 11 revalidation batches;
- second dry-run/apply: exactly 700 descriptions, 8 revalidation batches;
- final dry-run: exactly 10,188 eligible descriptions remain;
- PostgreSQL: 5,865 exact drafts, 16,415 published products, 34 priced products
  and zero indexable product URLs;
- PHPUnit: 4 tests, 41 assertions passed;
- queue worker: all 19 revalidation jobs completed without error;
- browser boundary sample `legacy-bitrix-9570`: exact title, rendered text,
  `/api/media/5368` at natural width 800 px, request-price state and
  `noindex, nofollow`.

## Next step

Continue the exact-description queue while implementing the staged P/N and
title-fact candidate registry for 2,188 thin laptop records. This creates a
high-throughput research queue without inventing facts or collapsing distinct
battery variants.
