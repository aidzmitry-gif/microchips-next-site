# RB OEM mobile-computer batteries — Wave202

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Outcome

Wave202 processed the next 237 B2B battery candidates from the Wave201 industrial queue in four bounded partitions:

| Partition | Rows |
|---|---:|
| Zebra / Motorola / Symbol | 151 |
| Honeywell | 42 |
| Datalogic | 26 |
| Intermec | 18 |
| **Total** | **237** |

The identity research is fail-closed. No new manufacturer/MPN, technical specification, price, stock state, media or Offer schema was applied in this wave.

## Evidence decision

The first pass considered `bitrix:12122` / `P1083277-002` safe. An independent live-source recheck rejected that decision:

- the current Zebra `Battery Test Summary Reports Where-Used` PDF is revision `2026-06-23`;
- the live two-page revision does not contain `P1083277-002`;
- a search-engine extract still exposes text from an older revision, but no immutable first-party snapshot and SHA-256 had been stored;
- the row is therefore `no_evidence / source_superseded`, `safe_to_apply=false`.

This correction prevents stale search-index text from becoming canonical catalogue identity. Five Zebra exact rows are prior Wave174 results and were explicitly marked `previously_processed`; they were not applied again.

Final research partition:

| Decision | Rows |
|---|---:|
| Previously processed | 9 |
| Compatibility only | 70 |
| Conflicting evidence | 19 |
| No reproducible exact evidence | 139 |
| **New safe applications** | **0** |

The 139 no-evidence total includes the source-superseded Zebra row. Replacement manufacturer/MPN fields are empty for every new unsafe row.

## Commercial and duplicate guard

The read-only Laravel/PostgreSQL guard checked all 237 current product records:

- products found: **237 / 237**;
- RB site products: **236** (`bitrix:12270` has no RB site product and is a previously processed row);
- current prices / currencies / `in_stock`: **0 / 0 / 0**;
- Offer schema / unsupported commercial claims: **0 / 0**;
- price-evidence rows / current price-evidence rows: **0 / 0**;
- media / verified published media: **0 / 0**;
- applied or legacy source drafts: **237**;
- automatic database mutations: **0**.

Four strict same-model, same-voltage, same-capacity Motorola/Symbol duplicate groups were found (eight cards):

1. `BTRYMC30LA | 3.7 | 2740` — `bitrix:12130` / `bitrix:24006`;
2. `BTRYMC30LA | 3.7 | 4800` — `bitrix:12146` / `bitrix:24007`;
3. `BTRY-MC32-52MA-01 | 3.7 | 5200` — `bitrix:12139` / `bitrix:24008`;
4. `BTRY-MC55EAB00 | 3.7 | 3600` — `bitrix:12142` / `bitrix:24009`.

They are handled through the existing noindex duplicate-collapse workflow: preserve the Motorola survivor, remove only the duplicate RB `site_product`, and retain a permanent local redirect. Canonical shared `products` are never deleted by this workflow.

The reviewed manifest was applied after a second dry-run:

- requested / collapsed: **4 / 4**;
- RB duplicate `site_product` rows removed: **4**;
- canonical `products` removed: **0**;
- permanent redirects created: **4**;
- idempotence rerun: **0 collapsed / 4 already_collapsed**;
- all four duplicate paths return **301** to the selected Motorola survivor;
- all four survivor pages return **200**.

## Import safety improvement

`catalog:apply-verified-oem-identities` now requires more than a live HTTPS URL:

- exact pinned Bitrix product name and `draft` status;
- one schema-null noindex page on every linked site;
- a readable local source snapshot with matching SHA-256;
- transaction locks for Product, SiteProduct, URL and SEO state;
- PostgreSQL advisory locking for the manifest/source pair;
- full staged-evidence checksum verification before idempotent success;
- revalidation for every linked site after a shared identity update.

This command still changes only blank manufacturer/MPN fields. It cannot add price, availability, schema, technical claims or publication state.

## Reproducible artefacts

- `docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence.csv`
- `docs/audits/generated/rb-wave202-honeywell-evidence.csv`
- `docs/audits/generated/wave202-oem-replacement-evidence.csv`
- `docs/audits/generated/rb-wave202-commercial-duplicate-guard.csv`
- `scripts/build-rb-wave202-zebra-evidence.py`
- `scripts/build-rb-wave202-honeywell-evidence.py`
- `scripts/build-wave202-oem-replacement-evidence.py`
- `scripts/build-rb-wave202-commercial-duplicate-guard.ps1`

## Verification

- combined Wave202 evidence and commercial-guard tests: **11 passed**;
- strict duplicate builder plus commercial-guard regression: **6 passed**;
- repeated commercial guard hashes are identical:
  - CSV `7F2F083601D1EA12ED94E2A91FAB8C880128698ECE3A7F6AD9F98FAE6CAB971F`;
  - JSON `2BCF06FE91C4CDB891BA85FEFDBA33C00C02F0AE47D66137F5880C24251F18A6`;
- OEM identity command: **5 tests, 42 assertions passed** on PHP 8.5.8;
- Laravel Pint: **2 files passed**;
- Next.js 16.2.10 production build and TypeScript: **passed**;
- Laravel production image build: **passed**;
- post-collapse SEO audit: **16,853 URLs, 97 redirects, 0 blockers**;
- database identity/commercial mutations in the evidence stage: **0**; the only Wave202 database change was the reviewed four-row duplicate collapse above.

The overall project readiness remains at the last objectively confirmed threshold of 60%. This wave improves catalogue safety and reduces the reviewed backlog, but it does not by itself satisfy the next weighted 70% gate.
