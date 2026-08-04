# RB mobile media attachment — wave 160

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 160 reused the prepared mobile assets and attached the exact count needed
to exceed the 70% threshold without relying on two-decimal rounding.

| Metric | Result |
| --- | ---: |
| Prepared eligible images before wave | 2,266 |
| Images attached | 1,642 (1,000 + 642) |
| Prepared eligible remainder | 624 |
| Revalidation batches | 18 |
| RB published products | 16,415 |
| RB products with displayable media | 11,491 |
| Safe local media coverage | 70.0030% |
| Mobile products with displayable media | 4,677 / 5,303 |

The prior wave report originally stated that 1,641 images were sufficient. A
pre-apply integer check found that 11,490 / 16,415 is still fractionally below
70%; the report was corrected and 1,642 images were attached instead.

## Verification

- PostgreSQL: 11,491 / 16,415 = 70.0030%;
- mobile category: 4,677 with media, zero priced, zero indexable;
- dry-run after attachment: exactly 624 eligible prepared images remain;
- browser page 389: 12 / 12 images loaded, zero broken images;
- browser boundary page 390: 9 valid images followed by three no-image cards,
  with zero broken requests; this matches the 4,677-card media boundary;
- sampled deep-page cards visually showed relevant mobile-battery images;
- sample `/api/media/11487`: HTTP 200, `image/jpeg`, private/no-store and
  `X-Robots-Tag: noindex, noarchive`;
- Horizon logs show all 18 revalidation jobs completed.

## Safety boundary

Only exact same-element Bitrix preview media was attached. The wave did not
change identity, descriptions, characteristics, price, stock or SEO
indexability. The remaining no-image cards are not assigned visually similar
assets without source evidence.

## Next step

The remaining prepared mobile set adds only 624 cards, so the next full 10%
coverage milestone will require a new bounded source category, most efficiently
the laptop replacement-battery slice. Before that larger transfer, catalogue
quality work can pivot to thin-page classification and source-backed content so
media coverage is not mistaken for overall SEO readiness.
