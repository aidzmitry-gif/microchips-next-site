# Wave242 — no-repeat identity, content, media and commercial-truth loop

Date: `2026-07-29`  
Site: `microchips-by`

## Outcome

Wave242 processed 267 previously held UPS-battery cards against new
manufacturer-primary evidence without replaying earlier URLs or snapshot
hashes.

- Delta: 59 identity PASS, 77 HOLD.
- CSB / Marathon / Leoch: 57 identity PASS, 74 HOLD.
- Total identities applied: **116**; normalized MPN ownership conflicts after
  apply: **0**.
- Source-backed descriptions applied: **113**. Three otherwise-safe Delta CGD
  identities remain without new prose because the pinned source does not state
  their technology.
- Official image audit: 44 products, 37 visual candidates and seven contact
  sheets; **0 PASS / 44 HOLD**. Family imagery, shared APC rasters, unreadable
  full MPN labels and missing documented commercial-reuse permission were not
  promoted.

The first generated manifests failed the real Laravel contract dry-run because
their builder tests checked only their own schema. The manifests were corrected
before any write: prohibited fields were removed, `locale=ru-BY` and
source-supported technology were added, and tests now check the actual PHP
allowlists. This adversarial failure was useful evidence; no failed dry-run
mutated product data.

## Apply and idempotence evidence

- Identity manifests: 59 + 57 records; apply filled 116 identities with zero
  commercial or publication changes.
- Description manifests: 56 + 57 records; apply wrote 113 descriptions and
  published no products.
- Identity repeat apply: 0 filled, 116 unchanged.
- Description repeat apply after full revalidation: 0 applied, 113 unchanged.
- Two runtime cards resolve with the new exact identity and text:
  - `bitrix:1442` — Delta CT 1210, AGM, 12 V, 10 Ah;
  - `bitrix:2732` — CSB GP121000, AGM, 12 V, 100 Ah.
  Both remain `noindex`, `on_request`, and without `Offer` schema.

Commercial control snapshot stayed identical:

| Metric | Before | After |
|---|---:|---:|
| Site products | 24,298 | 24,298 |
| Published site products | 16,816 | 16,816 |
| Numeric prices | 1,067 | 1,067 |
| Price sum | 1,616,436.49 BYN | 1,616,436.49 BYN |
| Current price evidence | 1,067 | 1,067 |
| Availability `on_request` | 24,298 | 24,298 |
| Applied descriptions | 1,508 | 1,621 |
| Blank manufacturers | 22,814 | 22,698 |

## Price and availability truth

All 1,067 current price-evidence rows were reconstructed and audited:

- source `legacy_site`: 1,067; source `one_c_x2`: 0;
- currency BYN: 1,067;
- duplicate product/reference and price/evidence mismatch counters: 0;
- every price was observed on `2026-06-23`, 36 days before this audit;
- Offer eligible: 0/1,067 because `on_request` is not independent stock
  confirmation.

The numeric price remains distinct from availability. Wave242 adds the evidence
date to the API/UI so a visitor sees that the price is historical and should be
confirmed; it does not fabricate `InStock` or add Offer schema.

## Readiness and no-repeat queue

- Content-complete cards: **395** (unchanged; exact reusable images remain the
  limiting gate).
- Strict-content-ready: **216** (unchanged).
- `source_backed_partial`: **968 → 1,081** (+113).
- No-repeat queue membership: **1,247**, exactly preserved from Wave241.
  - description present / verified image missing: **902**;
  - description missing / verified image missing: **345**.
- The unskipped live 10% queue contains 1,287 rows; the extra 40 are earlier
  reviewed HOLD rows and are deliberately not reintroduced.

Overall confirmed project readiness remains **60%**. This cycle closes 116
identity gaps, 113 description gaps and two interface defects, but verified
image coverage and country-launch gates do not yet justify another project-level
10 percentage points.

## Verification

- Combined Wave242 Python suites: 19 passed.
- Queue rollover test: included in the 19 passed; 1,247 unique IDs and exact
  Wave241 membership.
- Frontend catalogue/page/price-evidence suites: 31 passed.
- Backend price-evidence API checks: 2 targeted tests, 23 assertions passed
  against an isolated migrated SQLite database in PHP 8.5.8.
- TypeScript: `tsc --noEmit` passed.
- Next production build: passed.
- SEO audit with 512 MB: 16,853 URLs, 97 redirects, 0 blockers.
- RB HTML prototypes: 4/4 passed.
- Docker services: PostgreSQL, Redis, backend, worker, nginx and frontend
  healthy after rebuild.
- Runtime truth check: priced catalogue and product payloads expose
  `price_observed_at=2026-06-23`; the unpriced KM-300 P payload exposes null;
  an `on_request` product emits no Offer schema.
- Mobile visual regression: the category tree is collapsed by default,
  expands without a duplicate heading, and price evidence is visible on the
  product cards.

## Evidence

- `docs/imports/rb-verified-oem-identities-wave242-delta-2026-07-29.json`
- `docs/imports/rb-source-backed-descriptions-wave242-delta-2026-07-29.json`
- `docs/imports/rb-verified-oem-identities-wave242-leoch-marathon-csb-2026-07-29.json`
- `docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json`
- `docs/audits/generated/rb-enrichment-queue-wave242.csv`
- `docs/audits/generated/rb-full-content-readiness-wave242-after.csv`
- `docs/audits/generated/rb-wave242c-official-image-ledger.csv`
- `docs/audits/generated/rb-wave242d-price-freshness-ledger.csv`

No commit or push was performed.
