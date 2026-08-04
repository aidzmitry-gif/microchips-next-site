# RB duplicate and scope cleanup wave 110 — 2026-07-28

## Result

Six non-public RB market drafts were removed from the storefront scope. No
canonical product was deleted and no other country profile was changed.

- two exact traction-battery duplicate drafts were removed while their
  canonical survivors were retained;
- one loading/unloading service row was removed from product inventory;
- two complete electric forklifts were removed as outside the accumulator and
  reserve-power scope;
- one misleading forklift row containing the implausible “1600 tons” wording
  was removed rather than turned into a thin SEO page.

The exact decisions and survivor IDs are recorded in
`docs/audits/2026-07-28-rb-scope-exclusion-wave-110.md`.

## Safety and verification

- pre-apply query confirmed all six RB links were unpublished, `on_request`
  and unpriced;
- command dry-run validated all six requested links;
- apply result: six RB draft links excluded, zero canonical products deleted,
  zero published products changed;
- post-apply query: zero excluded RB links remain, all six canonical products
  remain, both duplicate-survivor RB links remain;
- RB site-product count changed from 7,143 to 7,137;
- published previews remain 100, descriptions remain 223, verified media
  remains 40 and current provenance-backed prices remain 57;
- SEO audit: 117 checked URLs, zero blocking issues;
- fixed enrichment baseline remains 7,286; eligible non-electronic products
  changed from 5,726 to 5,720; strict complete remains **40 / 7,286 = 0.55%**;
- queue remains 689 because it is defined as the deterministic gap from 40
  strict-complete cards to the fixed 729-card first-10% target.

## Reproducible evidence

- `docs/imports/rb-scope-exclusion-wave-110.csv`
- `docs/audits/2026-07-28-rb-scope-exclusion-wave-110.md`
- `docs/audits/generated/rb-enrichment-queue-wave-110.csv`
- `docs/audits/generated/rb-enrichment-queue-wave-110.summary.json`
