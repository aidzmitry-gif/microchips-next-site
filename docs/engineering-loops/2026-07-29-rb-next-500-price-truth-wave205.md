# RB next 500 and price truth — Wave205

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## No-repeat research queue

The B2B priority builder now accepts a pinned processed-register only when its path, expected SHA-256 and expected row count are supplied together. It rejects empty, duplicate, unknown and non-B2B IDs, `hold ↔ processed` overlap, and any held or processed ID leaking into the result.

The complete Wave174 queue is the processed-register for Waves174–204:

- processed records: **500**;
- processed SHA-256: `a4ed39b73d5f809d6d815cef68b6f31ad1704f4c0a6f8bedfdb550324a7fb7b7`;
- Wave205 records: **500 unique**;
- overlap with the first 500: **0**;
- Wave205 CSV SHA-256: `afbe1f9767f9e49de8bc51bee9f27a9bb3a372548f64f9365e976bf5d89f2344`;
- incomplete, unprocessed B2B candidates after selection: **3,394**.

The new queue contains 296 industrial-battery cards and 204 UPS-battery cards. Every card remains `safe_to_apply=false` until source evidence is evaluated.

## Source-research plan

All 500 selected cards currently have high thin-content risk. Grouping them before web research avoids one-product-at-a-time work:

| Research lane | Cards | Decision |
|---|---:|---|
| Delta + FIAMM + B.B. Battery + CSB | 100 | First-party catalogues are likely to cover whole series; research first |
| Panasonic + Ventura + MNB + Casil + Robiton + Minamoto | 104 | Claimed manufacturers, medium source likelihood |
| Motorola + Kenwood + Vertex + Icom + Baofeng + Symbol + Yaesu | 143 | OEM documents may prove device compatibility but not the replacement battery manufacturer |
| AT radio packs + cash-register packs + unresolved replacements/cells + Vector | 153 | Resolve the pack identity before spending web-research budget |

The first active official-source package is Delta/FIAMM followed by Panasonic/Ventura/MNB: **177 cards** in parallel, without publication or database mutation.

## Current price truth

The accepted commercial rule remains:

1. an exact, evidenced public price from the old site has priority;
2. otherwise an exact 1C-linked product may use `source price × 2`;
3. price never implies stock;
4. an Offer requires matching current evidence, visible price/currency and independently confirmed availability.

The current authoritative 1C inventory cannot supply a price batch:

| Measure | Count |
|---|---:|
| Non-group 1C rows | 9,123 |
| Positive price | 0 |
| Currency present | 0 |
| Price type present | 0 |
| Fully eligible BYN rows | 0 |
| Safe `1C × 2` candidates | 0 |

The raw 1C payload has the same zero counts, so this is not merely a parser omission.

Current RB price state:

- site products: **24,298**;
- products directly linked to a 1C external ID: **7,011**;
- approved Bitrix ↔ 1C candidates: **58**;
- visible numeric prices: **57**;
- published noindex previews with a numeric price: **34**;
- current evidence rows: **57 legacy-site / 0 one-c-x2**;
- price without evidence: **0**;
- evidence/value mismatch: **0**;
- duplicate current evidence: **0**.

All 57 prices come from the old-site commercial snapshot observed on 2026-06-23. They are evidence-backed but not a fresh 1C feed. A new `1C × 2` batch stays on hold until a fresh export includes positive price, `BYN`, price type and import timestamp.

## Verification

- priority-queue suite: **7 passed**;
- source-planner and price-audit suites: **5 passed**;
- hardened price SQL suite after the fail-closed numeric parser change: **3 passed**;
- live read-only SQL rerun reproduced all price and integrity counts;
- queue and source planner made **0 database mutations**;
- no price, availability, Offer or publication state was changed.

## Main artefacts

- `docs/audits/generated/rb-b2b-priority-queue-wave205.csv`
- `docs/audits/generated/rb-b2b-priority-queue-wave205.summary.json`
- `docs/audits/generated/rb-b2b-next-source-batch-wave205.csv`
- `docs/audits/generated/rb-b2b-next-source-batch-wave205.summary.json`
- `docs/audits/generated/rb-price-truth-wave205-summary.json`
- `docs/audits/generated/rb-price-truth-wave205-audit.md`
- `scripts/build-rb-b2b-priority-queue.py`
- `scripts/build-rb-b2b-next-source-batch.py`
- `scripts/audit-rb-price-truth.sql`

Wave205 creates the next reproducible work package and prevents repeated catalogue research. It does not raise overall readiness by itself because no new country launch gate or indexable commercial batch was completed.
