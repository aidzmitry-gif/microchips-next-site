# RB mobile media attachment — wave 159

Date: 2026-07-28. Site: `microchips-by`.

## Result

Wave 159 reused the already extracted and integrity-checked mobile assets from
wave 158. No Bitrix archive scan, file extraction or fuzzy image matching was
repeated.

| Metric | Result |
| --- | ---: |
| Prepared eligible images before wave | 3,901 |
| Images attached | 1,635 (1,000 + 635) |
| Prepared eligible remainder | 2,266 |
| Revalidation batches | 18 |
| RB published products | 16,415 |
| RB products with displayable media | 9,849 |
| Safe local media coverage | 60.00% |
| Mobile products with displayable media | 3,035 / 5,303 |

## Safety

The exact same-element Bitrix relationship and raster integrity had already
been verified by the wave 158 manifest. This wave only created
`legacy_exact_preview` rows for the next bounded set of products. It made no
changes to price, stock, identity, indexability or product facts.

The complete mobile category remains unpriced and non-indexable. Remaining
prepared assets are intentionally not attached until the next bounded cycle.

## Verification

- PostgreSQL: 9,849 / 16,415 = 60.00%;
- mobile category: 3,035 with media, zero priced, zero indexable;
- dry-run after attachment: exactly 2,266 eligible prepared images remain;
- browser page 250: 12 / 12 images loaded with non-zero dimensions, zero broken
  images and zero placeholders;
- visual review of deep-page cards showed model-relevant mobile-battery assets;
- sample `/api/media/9819`: HTTP 200, `image/webp`, private/no-store and
  `X-Robots-Tag: noindex, noarchive`;
- Horizon logs show all 18 revalidation jobs completed.

## Next step

The next 10% milestone needs 1,642 additional images. The prepared mobile
remainder of 2,266 is sufficient, so reaching 70% also requires no archive
rescan.
