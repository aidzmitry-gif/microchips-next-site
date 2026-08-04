# RB commercial data audit — Wave215-C

Read-only check on 2026-07-29. No commercial or publication field changed.

## Current commercial facts

- Site products: 24298; numeric prices: 57; current price-evidence rows: 57.
- Current evidence by source: legacy_site=57.
- Price integrity: without current evidence=0; value mismatch=0; duplicate current evidence=0.
- Availability distribution: on_request=24298. There is no separate availability-evidence table.

## 1C × 2 rule

The implementation applies multiplier `2` only to provenance-backed `one_c_x2` rows and does not alter availability. The current 1C inventory has 0 positive prices, 0 currencies, 0 price types and 0 fully eligible BYN rows. Therefore the rule is represented safely in code but is **not usable on current data**.

## Deterministic next path

Wait for a fresh 1C commercial export. Then generate a 100-row maximum batch ordered by `products.external_id`, requiring: exact direct external-ID link, positive BYN price, non-empty price type, timestamp, `availability=on_request`, and no current legacy-site evidence. Run the price importer as a dry run only; it may update price evidence but must not change availability, publication, or create an Offer.
