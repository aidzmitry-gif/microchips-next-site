# RB full Bitrix catalogue staging — wave 148

Date: 2026-07-28  
Branch: `codex/readiness-80-loop`

## Outcome

The complete 17,207-row Bitrix registry is now staged in PostgreSQL as one
namespaced evidence row per Bitrix ID. This replaces the incorrect assumption
that the earlier 1,569-row batteries/UPS snapshot represented the whole site.

The staging contract is intentionally non-releasing:

- no Product or SiteProduct is created;
- no product is published;
- no URL, SEO record, price, stock assertion or offer is created;
- no duplicate candidate is merged or deleted;
- electronic components remain excluded from publication;
- every active row is assigned to exactly one existing target SEO leaf;
- every row carries a deterministic checksum and the whole manifest carries a
  SHA-256 hash.

## Full-catalogue status

| Transfer status | Count |
|---|---:|
| legacy-only draft candidate | 16,173 |
| hold: 1C collision | 574 |
| excluded: electronic components | 295 |
| hold: linked identity candidate | 87 |
| hold: duplicate candidate | 52 |
| excluded: inactive legacy | 18 |
| existing exact 1C link, non-electronics | 8 |
| **Total** | **17,207** |

The counts differ from the raw identity-status registry because scope is
applied first: some exact links, duplicate candidates and unresolved rows are
inside the excluded electronic-components branch.

## Category coverage

All 17,189 active rows mapped to exactly one of 17 leaf categories. Largest
groups are:

- replacement mobile: 5,506;
- replacement laptops: 3,348;
- primary cells: 1,630;
- rechargeable cells: 1,125;
- batteries for UPS: 1,097;
- industrial batteries: 918;
- replacement photo/video/audio: 880;
- power systems: 687.

The remaining rows are distributed across the other existing approved leaves;
the generated summary contains the complete distribution.

## Implemented artifacts

- `scripts/build-full-bitrix-staging-manifest.py`;
- `scripts/tests/test_build_full_bitrix_staging_manifest.py`;
- `backend/app/Console/Commands/StageFullBitrixCatalog.php`;
- `backend/tests/Feature/StageFullBitrixCatalogTest.php`;
- `docs/imports/rb-full-bitrix-staging-wave148-2026-07-28.json`;
- `docs/imports/rb-full-bitrix-staging-wave148-2026-07-28.summary.json`.

Database evidence:

- import run: `763`;
- source: `bitrix_full_catalog_snapshot:microchips-by`;
- staged rows: 17,207;
- failed rows: 0;
- rows with publication mutations: 0;
- manifest SHA-256:
  `0d364128146d25fc8895525d50b9162011bf1b9c0d81b33f6efaef794a535a02`.

## Verification

- Python builder tests: 2 passed.
- Python compile: passed.
- PHP syntax: command and feature test passed `php -l`.
- Production-image build: passed.
- Full dry-run: 17,207 accepted, exact status/category totals matched.
- Apply: 17,207 staged, zero catalogue mutations.
- Immediate second apply: `unchanged=true`; no second run or duplicate evidence
  rows were created.
- PostgreSQL audit: run 763 has exactly 17,207 rows and zero publication
  mutations.

The production image intentionally has no development test command, while the
host PHP lacks `mbstring`; therefore the Laravel feature test file was syntax
checked but not executed in this environment. The production command itself
was exercised end-to-end by dry-run, apply and idempotency apply against the
real PostgreSQL database.

## Next gate

Create the next bounded command from run 763 that converts only
`legacy_only_draft_candidate` rows into unpublished, namespaced Product and
SiteProduct drafts in batches of hundreds. It must retain the checksum/run
lineage, the single category assignment and the existing no-merge/no-publication
invariants. Public noindex pages remain a later, separately verified gate.

