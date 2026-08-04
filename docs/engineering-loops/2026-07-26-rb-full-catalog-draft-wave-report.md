# RB full catalogue draft-wave report — 2026-07-26

## Result

- 1C source snapshot: `nomenclature_20260719.csv`, SHA-256
  `03a2aa7469d818697608d9e79e077fe64e49b13ae5b6432b9631c663df4e9bf1`.
- Source product rows: **9,123**.
- Excluded before staging: **39** rows matched the non-product rule
  (delivery, service, invoice/complaint-book wording). They have no product
  drafts, URLs, prices or indexable pages.
- Imported as RB **unpublished drafts**: **9,084** products and **9,084**
  `site_products`.
- Public RB products after the run: **0**.
- Open duplicate conflicts after the run: **0**.

## Safety rule applied

Each accepted record uses only its stable 1C `external_id` at this stage.
No article was guessed as SKU/MPN, no fuzzy Bitrix-to-1C pair was merged, and
the staging process stopped on a count mismatch, validation error or duplicate
conflict. Internal `draft-<hash>` slugs are intentionally non-SEO placeholders
and must not be exposed until the SEO/category gate creates final URLs.

## Additional completed catalogue evidence

- Full SEO tree: 19 unpublished RB categories.
- Manufacturer/source-attributed editorial material: 27 unpublished product
  description drafts.
- Legacy Bitrix rows without a proven canonical identity remain unmerged;
  they are research candidates, not automatically created duplicate products.

## Next release gates

1. Assign every draft to one approved leaf in the 19-category SEO tree.
2. Generate final slugs only where a product has a stable identity and an
   approved category; do not expose the internal draft slugs.
3. Enrich priority product cards with primary/brand-authorized technical
   sources and rights-cleared images, then visually inspect representative
   cards and long-name/mobile states.
4. Run SEO release audit before any product, category or URL becomes public.
