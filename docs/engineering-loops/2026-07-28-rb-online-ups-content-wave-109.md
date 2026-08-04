# RB online UPS content wave 109 — 2026-07-28

## Scope

This loop processed two new 1C UPS products for which an exact current
manufacturer page was available. Electronic components, already completed
products, ambiguous model matches and products without primary-source facts
were excluded before any write.

The exact `КА` identifiers were checked in both `one_c_nomenclature_items` and
the RB catalogue. Both records were unpublished, had `on_request`
availability, no price and no previous source-backed description.

## Applied content

| 1C external ID | Manufacturer | MPN | Verified facts |
| --- | --- | --- | --- |
| `КА-00003387` | Парус электро | `СИПБ1КА.10-11` | online double conversion; 1000 VA / 1000 W; 1/1 phase; 110–300 V input; pure sine; 0 ms transfer; 8 × IEC 320 C13; Rack/Tower 2U; 440 × 460 × 86.5 mm; 15.9 kg; manufacturer article `АПСМ.435241.024-01` |
| `КА-00005734` | Сайбер Электро | `ЭКСПЕРТ-II-1000Р` | online double conversion; 1000 VA / 1000 W; 1/1 phase; 80–300 V input; pure sine; 0 ms transfer; 8 × IEC C13 and 2 × IEC C19; Rack/Tower 2U; 438 × 88 × 430 mm; 13.5 kg |

Primary evidence:

- Парус электро exact product page:
  `https://parus-electro.ru/catalog/ibp-peremennogo-toka/sipb1ka_10_11/`;
- Сайбер Электро exact product page:
  `https://xn--80acmarjf0aodcu3l.xn--p1ai/catalog/ibp-po-sfere-primeneniya/ibp-dlya-ofisa/ekspert-ii-1000r/`.

No stock, local warranty, included accessory or price was inferred. Both
products were published only as `noindex, nofollow` previews in the existing
verified UPS category.

## Adversarial decisions

- Each new normalized `manufacturer + MPN` pair occurs exactly once in the RB
  catalogue.
- Delta `UPS302R2RT2B035`, CyberPower `UT1500EIG`, Inelt Gamma/Sigma and
  anonymous battery rows remain on hold because an exact primary source or a
  sufficiently strong identity match was not available.
- A separate audit classified 35 later queue rows as 22 safe, 7 hold and 6
  reject. Those decisions were not silently applied in this content wave;
  duplicate, service and category-mismatch rejects are reserved for the next
  reversible exclusion cycle.
- The media audit found zero new safe exact-model images in the inspected
  range. No external image was imported without model and rights evidence, so
  both cards intentionally keep the placeholder.

## Price policy

The accepted rule is unchanged:

1. a verified current legacy-site price is retained with multiplier `1`;
2. if no legacy price exists and a usable 1C price exists, the raw 1C price is
   multiplied exactly once by `2`, with source value, multiplier and provenance
   recorded;
3. without either source the card shows `Цена по запросу`.

The current 1C snapshot contains **0** usable price rows with the required
price, currency and price-type evidence. No price was invented in this wave.

## Applied counters

- RB site products: 7,143;
- published noindex previews: 100 (`+2`);
- source-backed descriptions: 223 (`+2`);
- verified published media products: 40 (`+0`);
- current prices with provenance evidence: 57 (`+0`);
- strict non-electronic content-complete cards: **40 / 7,286 = 0.55%**;
- remaining fixed first-10% enrichment queue: 689 records.

The strict completion count did not increase because the two new cards do not
yet have source-authorized, visually verified media.

## Verification

- manifest validation: two description rows and two preview rows with equal ID
  sets, unique IDs and unique slugs;
- description dry-run and apply: two valid drafts; repeat staging: zero created,
  two unchanged;
- preview dry-run and apply: two products, zero indexable URLs, zero `Offer`
  schemas and zero priced products; repeat result identical;
- normalized `manufacturer + MPN` database check: two groups, one product in
  each group;
- browser SSR on both pages: one H1, self path in canonical, `noindex,
  nofollow`, `Цена по запросу`, no `Offer`, no 404, no horizontal overflow and
  an explicit image placeholder;
- model-specific facts verified in rendered HTML: Парус article, input range
  and mass; Сайбер input range, output count and mass;
- SEO audit: 117 URLs, zero blocking issues;
- enrichment queue rebuilt using the fixed baseline 7,286 with
  `seo:electronic-components` excluded: 40 complete and 689 remaining.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-109-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-109-2026-07-28.json`
- `docs/audits/generated/rb-enrichment-queue-wave-109.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-109.summary.json`
