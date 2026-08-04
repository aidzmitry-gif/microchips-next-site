# RB catalogue wave 197 — FIAMM FIT dealer-backed enrichment

Date: 2026-07-29  
Market: `microchips-by` (`ru-BY`)  
Scope: 6 existing Bitrix UPS-battery cards; no new Product, exact MPN, price, stock claim or image was created.

## Result

- Six FIAMM FIT cards received source-backed 12 V, capacity and VRLA AGM facts under the deliberately limited `dealer_backed / model_core` evidence policy.
- `12FIT40`, `12FIT100/23` and `12FIT150` use the 2022 FIT catalogue. Older `12FIT90`, `12FIT100/19` and `12FIT130` use the official representative's current replacement table for the voltage/capacity facts only.
- All six cards are assigned only to `catalog/industrial-batteries/batteries-ups` and remain noindex previews with `availability=on_request`, `price=null` and no `Offer` schema.
- Dealer evidence does not establish a canonical MPN. All six `products.mpn` values remain null, so the workflow did not collapse or create identities from model text.

## Sources

- Current FIT catalogue: `https://www.fiamm.ru/data/Catalogue/2022/FIT_web.pdf`
- Official representative replacement table: `https://www.fiamm.ru/services/faq/zaryadit-accumulyator.html`
- Publisher status evidence: `https://www.fiamm.ru/` identifies ООО «ФИАММ Индастриал РУС» as an official FIAMM representative.

The replacement table also distinguishes archival models from current analogues, but lifecycle/analogue fields were not imported because the dealer-backed policy permits only bounded technical voltage/capacity facts. This prevents a distributor statement from silently becoming canonical manufacturer identity or commercial availability.

## Verification

- Live preflight: 6/6 exact Bitrix rows exist; all have `legacy_only_draft_candidate`, source run `763`, no SKU/MPN collision and no price.
- Description dry-run `898` and apply `899`: 6 rows refreshed, 0 unchanged.
- Content dry-run `900` and apply `901`: 6 descriptions applied, 0 publication or commercial-field changes.
- Preview dry-run/apply: 6 products, 2 category nodes, 0 verified-price products, 0 indexable URLs and 0 offers.
- Wave verifier: 6/6 products, 6 distinct paths, 0 price-evidence rows, 0 duplicate MPN groups — PASS.
- PostgreSQL: 6 published, 6 `on_request`, 6 null prices, 6 null MPNs, 6 and only 6 target-category links, 6 applied dealer-backed drafts.
- RB SEO audit after apply: 16,858 URLs, 52 redirects, 0 blocking issues — PASS.
- Runtime samples `12FIT40`, `12FIT100/19` and `12FIT150`: HTTP 200, self-canonical, noindex, source-backed 12 V/capacity visible, no numeric price and no `Offer`.
- Shared PHP safety suite from wave 196 remains green: 36 tests, 116 assertions; Pint 6 files — PASS.

## Readiness

This wave increases verified B2B content coverage but does not cross the next whole-project 10% threshold. Confirmed overall readiness remains 60%; current commercial facts, image-rights verification, broader identity resolution and production launch gates remain incomplete.
