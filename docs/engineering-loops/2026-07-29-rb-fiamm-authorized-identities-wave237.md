# RB FIAMM authorised identity closure — Wave237

Date: 2026-07-29  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

Wave237 closes a material part of the remaining FIAMM identity gap without
repeating the earlier 106-card review. The builder consumes only the 79
`exact_local_text_unique` rows from the pinned Wave233 ledger. Each candidate
must additionally occur as an exact bounded model in one of six newly pinned
FIAMM catalogue PDFs.

- 79 previously reviewed, collision-free candidates reused;
- 47 exact authorised-catalogue matches applied;
- 32 candidates held because the exact model is absent from the pinned PDFs;
- 27 other Wave233 rows were never reconsidered: 23 lack exact local evidence
  and four collide with an existing canonical product;
- FIAMM rows in the current enrichment queue: 106;
- FIAMM rows with canonical identity after the wave: 47;
- FIAMM rows still lacking MPN: 59.

No new sellable product was invented from internet research. This wave improves
identity evidence for existing catalogue cards only.

## Authority chain

The previous package correctly treated FIAMM Russia as distributor evidence
and therefore remained review-only. Wave237 does not relabel that evidence as a
manufacturer source. Instead, Laravel now supports the explicit source kind
`official_authorized_distributor_catalogue` with additional fail-closed rules:

1. the authority URL must be HTTPS and use the same host as the catalogue;
2. both catalogue and authority snapshots must be SHA-256 pinned;
3. the authority snapshot must contain the exact authorization statement;
4. generic manufacturer evidence is rejected if it carries distributor fields;
5. only blank manufacturer/MPN fields may be filled on visible noindex drafts;
6. the existing global MPN/SKU collision guard remains unchanged.

Pinned authority page: `https://www.fiamm.ru/about/about-company/`, which
identifies FIAMM Industrial RUS as the official authorised distributor of
FIAMM Energy Technology S.p.A. for Russia, the Customs Union and CIS.

## Application evidence

- Manifest: `docs/imports/rb-verified-oem-identities-wave237-fiamm-2026-07-29.json`
- Manifest SHA-256: `85faeabdb97e269018907dacb1f9e4798dca990ad58c925f092ad2577af00ee3`
- Dry-run: 47 records accepted, zero mutations.
- Apply: 47 identity rows filled.
- Idempotence rerun: 0 filled, 47 unchanged.
- Import run: 1026, 47 reviewed evidence rows.
- Database verification: all 47 products exactly match manifest manufacturer
  and MPN values.
- Affected site products: 47 published noindex previews, 0 priced, 47
  `on_request`.
- Global commercial state remains 57 priced rows and 24,348 `on_request` rows.

No price, stock, product name, technical attribute, media, URL, schema or
publication field was changed.

## Parallel no-repeat audits

- Delta: 142 blank-MPN queue rows audited; zero safe applications. Twenty rows
  collide with current canonical identities, six exact CT models belong to the
  official motorcycle/starter series rather than the UPS category, and 116
  lack pinned exact primary evidence.
- Panasonic: 63 blank-MPN rows audited. Fifty-seven package/terminal variants
  were already handled in Wave200. Three active 1C products (`BR2032`,
  `CR2012`, `CR2450`) have exact pinned Panasonic evidence and no current
  identifier collision, but the existing Bitrix-draft command intentionally
  cannot mutate active 1C products. Three more remain without local snapshots.

These audits produced no writes and prevent the next cycle from repeating the
same research.

## Readiness and SEO

- Eligible published site products: 16,816.
- Content-complete cards: 392 (unchanged).
- Strict-content-ready cards: 213 (unchanged).
- Remaining 10% enrichment queue: 1,250 (unchanged; identity is an independent
  gate from verified media and description completeness).
- SEO release audit: 16,853 URLs, 97 redirects, 0 blockers.
- Prototype gate: 4 of 4 RB HTML prototypes passed.

## Verification

- Python deterministic builder test: **1 passed**.
- Laravel command Feature tests: **7 passed, 52 assertions**.
- PHP 8.5 syntax checks: both changed PHP files passed.
- Runtime dry-run, apply and idempotence checks passed against current
  PostgreSQL.
- No commit or push was performed.

## Next step

Use the same no-repeat queue to process the three exact Panasonic active-1C
identities through a dedicated active-product evidence path, then move to the
largest remaining manufacturer-primary description/media intersections. The
59 FIAMM holds must not be guessed from titles.
