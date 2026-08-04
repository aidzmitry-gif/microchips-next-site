# RB DELTA UPS content wave 113 — 2026-07-28

## Result

One previously unpublished 1C product was enriched from an exact official
model-specific manual and published as a safe RB noindex preview:

- `КА-00004707` — Delta Electronics Amplon RT
  `UPS302R2RT2B035`, 3000 VA / 2700 W.

Confirmed facts include online double-conversion topology, 1/1 phase, 0.9
output power factor, supported input/output voltage ranges, pure sine output,
six IEC C13 plus one IEC C19 receptacle, 72 V DC battery bus, sealed 12 V / 9
Ah batteries, 7-minute typical runtime at 75% load, 2U Rack/Tower form factor,
440 × 610 × 89 mm dimensions and 28 kg weight.

Primary evidence:

- `https://www.deltapowersolutions.com/media/download/Manual-UPS-RT-1-3kVA-new-en-us.pdf`;
- `https://www.deltapowersolutions.com/media/download/Leaflet-UPS-RT-1-3kVA-new-en-us.pdf`.

No model-neighbour facts, image, local warranty, price or stock were inferred.
The similar CyberPower `UT1500EIG` row was not processed because the current
official range does not expose an exact `UT1500EIG` product page; substituting
the Schuko `UT1500EG` would be a model error.

## Verification

- description dry-run and apply: one new draft and one applied description;
- repeat description staging: zero created, one unchanged;
- preview dry-run and apply: one product, zero indexable URLs, zero offers and
  zero verified-priced products; repeat dry-run identical;
- browser SSR: one H1, exact canonical path, `noindex, nofollow`, `Цена по
  запросу`, no `Offer`, no 404 and no horizontal overflow;
- rendered body contains the exact model, 3000 VA, 2700 W, 72 V DC,
  440 × 610 × 89 mm and 28 kg; the missing image remains an explicit
  placeholder rather than a generic UPS picture;
- SEO audit: 118 checked URLs, zero blocking issues.

## Counters

- RB site products: 7,137;
- published noindex previews: 101 (`+1`);
- source-backed descriptions: 224 (`+1`);
- verified published media products: 44;
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **44 / 7,286 = 0.60%**;
- remaining first-10% strict queue: 685.

Strict completion did not increase because no source-authorized exact-model
image is available for this item.

## Reproducible evidence

- `docs/imports/rb-source-backed-description-drafts-wave-113-2026-07-28.json`
- `docs/imports/rb-source-verified-preview-wave-113-2026-07-28.json`
- `docs/audits/generated/rb-enrichment-queue-wave-113.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-113.summary.json`
