# Engineering loop: RB B2B prototype and source slice

## Purpose and boundary

Baseline verified readiness is **38.25%**. This loop reduces the risk of
building the first Belarus B2B route from copied legacy markup or unreviewed
catalogue data. It is deliberately not a Belarus launch and it does not
connect 1C, Bitrix24, legal data, a production server, Search Console or
Yandex Webmaster.

The deliverables are:

1. a standalone, non-indexable HTML visual acceptance artifact for the first
   UPS/reserve-power category;
2. an explicit SSR/API/SEO/lead contract for transferring it into the existing
   Next.js and Laravel platform;
3. a reproducible, read-only Bitrix SQL extractor and quality evidence for a
   focused B2B review slice.

## Evidence produced

| Area | Verified result | Safety boundary |
| --- | --- | --- |
| Visual acceptance | `docs/prototypes/rb-b2b-catalog.html` models the desktop-first RB B2B category, product-comparison, filter, quote and FAQ states. | Its non-public status is governed by the [launch policy](../standards/launch-policy.md). |
| Static UI gate | `scripts/verify-rb-prototype.ps1` checks semantic structure and required prototype markers. | This is a pre-implementation guard, not an e2e or production SEO test; policy requirements are in the [launch policy](../standards/launch-policy.md). |
| Future implementation contract | `docs/frontend-rb-prototype-contract.md` maps each visual zone to `SiteResolver`, SSR metadata, site-scoped catalogue visibility and `POST /api/v1/leads/quote`. | It does not authorise publication; the [launch policy](../standards/launch-policy.md) is authoritative. |
| Source evidence | `extract-bitrix-b2b-catalog-slice.ps1` reads the 2026-06-23 SQL gzip snapshot locally using `GzipStream`, verifies SQL schema/tuple boundaries and checks offer infoblocks. The hardened `-WhatIf` reaches all five passes and then blocks on unresolved offers. | No database, network client, Bitrix mutation, Laravel publication or source modification occurs. |

## Source results and taxonomy decision

The extractor selected 6 direct UPS/industrial source sections and 219 sections
with descendants. It produced 2,856 review candidates: 2,849 active snapshot
rows, 7 inactive, all from infoblock 26, and 43,967 raw property values. Four
rows have no media reference; all 2,856 lack an extracted article/SKU/MPN value.

The broad industrial root contains unrelated radio, barcode-terminal,
medical-equipment and cash-register lines. The first RB prototype therefore
uses a **pre-review focus of 1,569 UPS/reserve-power candidates**, not the whole
2,856-row set. The figure uses every matched source-section membership. Its
1,445 primary-path candidates split as follows:

- 1,018 from `akkumulyatory/dlya_ibp` and AGM/GEL/OPzS children;
- 337 from `istochniki-pitaniya/ibp`;
- 90 from `akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya`.

Of these candidates, 1,445 have a primary section in the narrow focus, 81 have
a primary section elsewhere in the broad audit slice and 43 have a primary
section outside it. The latter group includes the Atlas Battery and Kanavno
LiFePO4 examples; it would have been lost by a primary-section-only headline.

The number is a review filter only. Each row is still `needs_review`.
Identity, offer-source and publication rules are defined in the
[launch policy](../standards/launch-policy.md).

## Verification record

| Check | Result |
| --- | --- |
| PowerShell parser + `extract-bitrix-b2b-catalog-slice.ps1 -RunSelfTest` | Passed |
| Hardened extractor `-WhatIf` against `D:\6 Проекты\microchips.by` | Completed five passes, then intentionally blocked: 12 active offers in 28/67 and no reconciled `CML2_LINK` parent. No output written. |
| Earlier local read-only export | Historical raw CSV/JSON remain ignored evidence only; the hardened extractor will not refresh them until the offer blocker is resolved. |
| `verify-rb-prototype.ps1` | Passed |
| Visual desktop review | Passed: main B2B hierarchy, category state, filters, comparison and request state are readable without copied Aspro markup |
| Visual mobile review | Passed after table containment fix: document and body width both equal the 375px viewport; only the comparison table may scroll locally |
| Full quality gate | Passed: PHP lint, Pint, PHPUnit **18 tests / 89 assertions**, Next.js production build and `docker compose config` |

## Readiness calculation

The documented 34.5% baseline was first corrected to **38.25%** because the
already-green remote CI proves the Part 3 test/CI criterion. This is an
evidence correction, not new functionality created by this loop.

This loop adds **0 new readiness points**, intentionally:

- Part 3 remains **65%**. The Bitrix snapshot validates source quality and
  catches the identity blocker, but it is not a representative 1C staging run
  with approved product identities, so its remaining data/integration criterion
  cannot be credited.
- Part 5 Belarus remains **0%**. A country starts counting only after all
  local commercial/legal, SEO/GEO, catalogue/CRM, regression and operating
  criteria are objectively confirmed. A visual prototype cannot substitute for
  those facts.

Verified total after the loop: **38.25%**.

## Next objective gate — Gate 0

Before the next implementation stage, obtain a 1С export or supplier price list
for at least **50 approved-focus products**. The evidence must allow stable
identity, SKU/MPN where applicable, category mapping and explicit duplicate or
missing-data disposition. Gate 0 permits only a small staging verification;
it does not permit a public RB listing or launch.

The complete requirements and country-launch blockers are in the
[launch policy](../standards/launch-policy.md).
