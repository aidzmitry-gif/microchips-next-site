# Wave242-D RB price-evidence freshness audit

This read-only, no-network audit reconstructs all **1,067** current RB price-evidence rows from the SHA-pinned Wave240 applied manifest (1,065 rows) plus the two separately reviewed exact links retained in Wave91. The union exactly matches the Wave240 post-apply receipt.

## Freshness and consistency

- Source: **1,067 `legacy_site`**, **0 `one_c_x2`**.
- Currency: **1,067 BYN**.
- Observed at: **2026-06-23T00:00:00+03:00** for every row.
- Age on 2026-07-29: **36 days**; all **1,067** fall in `31_60_stale_reconfirm`.
- Price types: **1,010** direct Bitrix legacy prices and **57** approved exact-link legacy prices.
- Reconstructed duplicate product IDs: **0**; duplicate source references: **0**.
- Wave240 current-state counters: price without evidence **0**, evidence/value mismatch **0**, duplicate current evidence **0**.

## Recommended policy (not applied)

1. **Visible numeric price**: keep distinct from availability. Evidence and BYN value must match. At 31-60 days, reconfirm before calling the number current; after 60 days, recommend suppressing the numeric value until refreshed.
2. **`on_request`**: remains the availability truth for these rows and must not be upgraded because a price exists.
3. **Offer eligibility**: **0/1,067**. `on_request` is not `InStock`; an Offer requires independently confirmed current stock plus a matching, fresh price/currency evidence record.

The age thresholds are a Wave242D recommendation, not an existing mutation or release-rule change. The current counters come from the SHA-pinned Wave240 post-apply receipt; no live database query was rerun in this bounded no-network follow-up.

## Artifacts

- `docs/audits/generated/rb-wave242d-price-freshness-ledger.csv` — full 1,067-row ledger.
- `docs/audits/generated/rb-wave242d-price-freshness.summary.json` — deterministic counters, policy and hashes.
- `scripts/audit-rb-price-truth.sql` — reused canonical read-only SQL, unchanged.

No database, price, availability, Offer schema, publication or application change was made.
