# RB OEM source batch — Wave206

Date: 2026-07-29  
Site: `microchips-by`  
Project readiness after the wave: **60% (unchanged)**

## Scope and result

Wave206 processes **185 new B2B cards** from the no-repeat Wave205 queue. The work was grouped by manufacturer and reused pinned source snapshots where possible.

| Research partition | Rows | Exact source match | Compatibility | Conflict | No evidence |
|---|---:|---:|---:|---:|---:|
| FIAMM + B.B. Battery + CSB | 38 | 23 | 11 | 3 | 1 |
| Delta | 62 | 27 | 0 | 19 | 16 |
| Panasonic + Ventura + MNB | 85 | 29 | 5 | 5 | 46 |
| **Total** | **185** | **79** | **16** | **27** | **63** |

An exact model token was not treated as automatic write authority. The final live Laravel/PostgreSQL gate allowed **48 evidence rows** and held 137:

- B.B. Battery manifest: 5;
- Delta manifest: 18;
- Panasonic/Ventura/MNB manifest: 25.

## Adversarial findings

### Duplicate and identity collisions

- `bitrix:1590 / HR33-12` already belongs to canonical 1C product `КА-00003582`;
- nine exact Delta models already belong to active 1C identities and were removed from the application manifest;
- three Ventura models (`GP6-12`, `GPL12-150`, `GPL12-200`) collide with active 1C identities;
- a Ventura peer pair is held by the full-registry duplicate guard.

These rows were not given a second canonical MPN. The initially generated Delta manifest was correctly rejected by the live `ProductIdentityGuard`; the builder was then fixed to pin live collision evidence, and the manifest was reduced from 27 to 18 rows before any write.

### Source and factual conflicts

- 18 Delta CT models are officially motorcycle/starter batteries and were excluded from the non-automotive B2B scope;
- Delta `DTM 1215`: legacy title says 15 Ah, current official source says 14.5 Ah;
- FIAMM `12FLB400P`, `12FLB450P` and `12FGL80` have legacy capacity conflicts;
- FIAMM evidence from an official distributor can validate technical facts but was not allowed to promote canonical manufacturer/MPN;
- Panasonic/Ventura/MNB rows without an exact first-party model token remain holds;
- compatibility documents never identify an aftermarket battery as the device OEM's own product.

## Safe application

Three manifests passed the unchanged `catalog:apply-verified-oem-identities` dry-run and were applied:

| Manifest | Rows | Newly filled | Already identical | SHA-256 |
|---|---:|---:|---:|---|
| B.B. Battery | 5 | 5 | 0 | `72f3f1ac60bd9720294fede943c826d13a01272422c500f65fc8560aa1df2afb` |
| Delta | 18 | 10 | 8 | `c04a49c94a716d5ea3d90ac55165811c4d7bdb39576ee3d89e07fb3d0baf45d7` |
| Panasonic/Ventura/MNB | 25 | 25 | 0 | `73bfc5abd4649ec4b2c5982ee78b2508f3ce1e0fc9d8ca2cf7af7d9421dd6d0a` |

Total new canonical identity fields filled: **40**. Eight Delta rows already contained the same identity and were revalidated without mutation. Idempotence reruns returned `0 filled / 5 unchanged`, `0 / 18`, and `0 / 25`.

Import runs `925`, `926` and `927` are completed and contain **48 reviewed evidence rows**. No product name, SKU, price, availability, technical specification or publication field was changed.

## Runtime and SEO verification

- all 48 affected products have exactly one RB site URL;
- indexable URLs among them: **0**;
- indexable SEO rows: **0**;
- non-null Product/Offer schema rows: **0**;
- five B.B. runtime pages and six representative Delta/Panasonic/Ventura/MNB pages return HTTP **200** and `noindex, nofollow`;
- final SEO audit: **16,853 URLs, 97 redirects, 0 blockers**.

## Tests

- FIAMM/B.B./CSB evidence + manifest: **6 passed**;
- Delta evidence + corrected live-collision manifest: **10 passed**;
- Panasonic/Ventura/MNB evidence + manifest: **6 passed**;
- total targeted Wave206 tests: **22 passed**.

## Main artefacts

- `docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv`
- `docs/audits/generated/rb-delta-wave206-official-evidence.csv`
- `docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv`
- `docs/imports/rb-verified-oem-identities-wave206-bb-2026-07-29.json`
- `docs/imports/rb-verified-oem-identities-wave206-delta-2026-07-29.json`
- `docs/imports/rb-verified-oem-identities-wave206-panasonic-ventura-mnb-2026-07-29.json`
- `docs/audits/evidence/wave206-delta-current-db-collisions.json`
- `docs/audits/generated/wave206-live-identity-collisions.json`
- `docs/audits/sources/wave206-fiamm-bb-csb/`
- `docs/audits/sources/delta-wave206/`
- `docs/audits/sources/wave206-panasonic-ventura-mnb/`

Wave206 materially improves identity correctness for the next 500-card queue, but it does not raise overall project readiness: verified media, manufacturer-primary descriptions, current prices and stock remain independent release gates.
