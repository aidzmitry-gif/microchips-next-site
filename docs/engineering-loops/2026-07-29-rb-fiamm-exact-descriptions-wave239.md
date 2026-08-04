# RB FIAMM exact descriptions — Wave239

Date: `2026-07-29`  
Site: `microchips-by`  
Overall confirmed project readiness: **60% (unchanged)**

## Outcome

Wave239 replaces legacy-preview evidence with exact, source-backed technical
descriptions for 29 already-identified FIAMM products. The scope is frozen from
the Wave237 identity manifest and the Wave238 enrichment queue; 18 FIAMM cards
with an applied description and 59 unresolved identity holds are excluded.

Each accepted MPN occurs once as a bounded table row on page 2 of one of five
SHA-256-pinned FIAMM manufacturer brochures (FG, FGH/FGHL, FGL, FLB and SLA).
Safe fields include series, AGM/VRLA technology, voltage, capacity, dimensions,
mass, terminal type and direct application notes; FLB rows also include the
published 15-minute power value. No price, availability or warranty fact is
present in the package.

The brochures are FIAMM Energy Technology S.p.A. materials preserved from the
authorised FIAMM Industrial RUS host. The source snapshots, URLs and hashes are
recorded in the generated ledger rather than inferred from product titles.

## Adversarial correction before apply

The first generated manifest was not applied. Review found that formatting a
decimal with unconditional `rstrip("0")` corrupted integer facts ending in
zero (`820 → 82`, `210 → 21`, `1500 → 15`). The formatter was corrected to
strip zeros only after a decimal point, and regression assertions now pin
representative values from every risky SLA/FGL row.

Product display names are rebuilt from the same exact source facts, for example:

- `2SLA800` → `Аккумулятор Fiamm 2SLA800 (AGM, 820Ah)`;
- `12FGL80` → `Аккумулятор Fiamm 12FGL80 (AGM, 80Ah)`;
- `2SLA2000` → `Аккумулятор Fiamm 2SLA2000 (AGM, 2000Ah)`.

This removes contradictory legacy capacities instead of copying them into the
new catalogue.

## Application evidence

- Manifest: `docs/imports/rb-source-backed-descriptions-wave239-fiamm-2026-07-29.json`;
- Manifest SHA-256: `8fcfeacfe40e85976d5f4367beb3444fb32f494ab4c87332ba5e8527d914a830`;
- staging dry-run with explicit legacy refresh: 29 refreshed;
- staging apply run: `1030`, 29 refreshed, none published;
- description dry-run: 29 applicable, zero commercial/publication changes;
- description apply run: `1032`, 29 applied;
- idempotence runs `1033–1034`: 0 changed, 29 unchanged.

Database verification confirms 29/29 latest drafts are applied
`manufacturer_primary`, 29/29 site cards remain published noindex previews,
29/29 remain unpriced and `on_request`, and all 29 still have null Offer schema.

## No-repeat parallel audit

- EnerSys media: 245 current rows reviewed against all existing Wave229–234
  artifacts. Fifteen prior visual/shared-hash holds were excluded; 230 generated
  cards have no saved discrete exact-model manufacturer asset. New PASS: 0.
- Blank manufacturer cohort: 462 rows. Of these, 461 were already reviewed in
  Wave233–234 (32 applied PASS, 429 HOLD); the only residual `Delta GEL 12-45`
  belongs to a previously held duplicate cluster. New PASS: 0.

These results prevent future cycles from repeating expensive identity or image
research without new source evidence.

## Readiness and SEO

- eligible published RB products: 16,816;
- source-backed partial cards: 898 → 927 (**+29**);
- legacy-content-preview cards: 14,672 → 14,643 (**−29**);
- content-complete cards: 392 (unchanged: exact images are still missing);
- strict-content-ready cards: 213 (unchanged);
- remaining 10% enrichment queue: 1,250 (composition advanced, size unchanged);
- SEO audit: 16,853 URLs, 97 redirects, 0 blockers.

Overall project readiness remains 60% because this is a verified content-depth
improvement, not completion of an additional weighted project part or a full
10-percentage-point catalogue gate.

## Verification

- deterministic Python builder: **5 tests passed**;
- Laravel manufacturer-primary stage/apply regression: **21 tests, 99 assertions**;
- runtime staging dry-run/apply, description dry-run/apply and idempotence passed;
- regenerated Wave239 queue and full readiness audit;
- no commit or push was performed.

## Next step

The bottleneck is now exact media, not text. Continue with a no-repeat media
acquisition package for existing high-value B2B identities; do not create new
internet products until the migrated catalogue's priority cards have verified
images and complete commercial truth.
