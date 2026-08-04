# RB DELTA correction and media wave 111 — 2026-07-28

## Result

This wave did not repeat the already completed identity, category, price or
preview work for four DELTA products. A pre-write database audit proved that
all four already had unique 1C ↔ Bitrix identities, applied descriptions,
published noindex previews, categories and legacy-site price evidence.

The remaining useful work was completed:

- four exact-model, company-owned legacy images were visually verified and
  published;
- two stale product descriptions were corrected against current exact-model
  primary pages;
- all four cards now satisfy the strict content-plus-media gate.

## Source-backed corrections

`КА-00002817` DELTA DT1233 was corrected from the previous 10.3 kg / Ø8 mm /
3–5 year values to the current exact-model evidence: 10.1 kg, Ø6 mm terminal
and 5-year design life. Its body and full heights are now separated as
197 × 131 × 163 mm and 180 mm.

`КА-00003468` DELTA DTM1226 was corrected from 9.2 kg / 6 years to 8.9 kg /
8 years. C20, C10 and C5 capacities, maximum charge/discharge currents and
temperature ranges were added from the current model page.

Primary sources:

- `https://energon.ru/akb/stationary-batteries/st-delta/delta_dt/delta_dt_1233/`;
- `https://energon.ru/akb/stationary-batteries/st-delta/delta_dtm/delta_dtm_1226/`;
- `https://energon.ru/akb/stationary-batteries/st-delta/delta_cgd/delta_cgd_1208/`;
- `https://energon.ru/akb/stationary-batteries/st-delta/delta_cgd/delta_cgd_1233/`.

The two refreshed applied drafts were staged only through the explicit
`--refresh-existing --refresh-applied` path and then applied separately. No
price, availability or publication state was changed by the correction.

## Visual media proof

Four archive members were extracted from
`microchips_upload_20260623.tar`. Their SHA-256 values matched the manifest,
and machine-vision inspection confirmed the exact physical labels:

| 1C ID | Visible model | Visible rating |
| --- | --- | --- |
| `КА-00002817` | DELTA DT 1233 | 12V 33Ah |
| `КА-00003468` | DELTA DTM 1226 | 12V 26Ah |
| `КА-00003766` | DELTA CGD 1208 | 12V 8Ah |
| `КА-00003445` | DELTA CGD 1233 | 12V 33Ah |

Every asset visibly carries the Microchips watermark and originates from the
company-owned Bitrix upload backup. This is the recorded reuse basis. Three
older external manufacturer-image candidates remain pending and unpublished;
they were not promoted because they have no recorded reuse basis.

## Price policy

The four cards retain their current legacy-site prices: 228.00, 181.00, 60.30
and 237.00 BYN. Legacy prices use multiplier `1`. The `1C × 2` fallback is not
used for these products because the current 1C snapshot has no raw price,
currency or price-type evidence for them.

## Verification

- media dry-run: four validated imports; apply: four imported and published;
  repeat dry-run: zero imports, four unchanged;
- corrected description staging: two existing applied drafts refreshed;
  apply dry-run: two valid corrections; apply: two changed products;
- normalized `manufacturer + MPN` check: one RB product for each of DT1233,
  DTM1226, CGD1208 and CGD1233;
- browser SSR on all four pages: one H1, exact canonical path, `noindex,
  nofollow`, expected provenance-backed price, no `Offer`, no 404 and no
  horizontal overflow;
- each `/api/media/{id}` image completed with a positive natural width; no
  placeholder remained; corrected model-specific facts were visible in the
  rendered HTML;
- SEO audit: 117 checked URLs, zero blocking issues.

## Counters

- RB site products: 7,137;
- published noindex previews: 100;
- source-backed descriptions: 223;
- verified published media products: 44 (`+4`);
- current prices with provenance evidence: 57;
- strict non-electronic content-complete cards: **44 / 7,286 = 0.60%**
  (`+4` cards);
- remaining fixed first-10% enrichment queue: 685 (`−4`).

## Reproducible evidence

- `docs/imports/rb-source-backed-description-corrections-wave-111-2026-07-28.json`
- `docs/imports/rb-verified-legacy-images-wave-111-2026-07-28.json`
- `docs/audits/2026-07-28-rb-delta-media-visual-evidence-wave-111.md`
- `docs/audits/generated/rb-enrichment-queue-wave-111.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-111.summary.json`
