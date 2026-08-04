# Wave131 guarded 1C recovery importer

`catalog:recover-wave131-site-products` is a fail-closed recovery command for the immutable 7,015-row Wave131
SiteProduct snapshot. It accepts only `microchips-by`, pins the Wave131 and Wave133 snapshot hashes, pins the
19-wave manifest and every wave CSV hash, checks the manifest's original 1C source hash, and pins the refresh-2
SEO assignment CSV. Counts, headers, wave boundaries, external-ID uniqueness and subset topology are validated
before any transaction starts.

The 558 Wave133 rows must already exist as their exact safe recovery state and are never rewritten. The remaining
6,457 rows use only the 1C external ID as identity and the pinned wave CSV for name and slug. Missing Products are
created with status `active`; SiteProducts are always unpublished, `on_request`, without price, SEO or URL. Existing
rows are accepted only when already exact and otherwise cause a transaction-wide failure.

Category links use only an exact refresh-2 assignment whose current `SiteCategory` exists. Otherwise the draft is
left unpublished and unclassified. Raw legacy category `410` is never consulted or created.

## Pinned categorization counters

- Full 7,015 scope: 5,876 assigned, 1,139 unclassified, 925 assignment-backed electronics.
- New 6,457 recovery rows: 5,388 assigned, 1,069 unclassified, 925 electronics.
- Immutable Wave133 adds three already-existing electronics links; therefore the resulting database contains 928
  electronics links while the authoritative assignment count remains 925.

These counters are executable fail-closed gates in the command, not report-only observations.

## Verification

The real 7,015-row scenario passed in SQLite `:memory:`: Wave133 test recovery, Wave131 dry-run rollback, creation
of exactly 6,457 missing Products and SiteProducts, field-by-field verification of every new row, preservation of all
558 Wave133 rows, exact categorized/unclassified/electronics counts, zero category `410`, URLs, prices, SEO and
publication, an idempotent second run, and conflict refusal. PHPUnit: **1 test, 64,604 assertions, exit 0**.

No live database command, apply, commit or push was performed.
