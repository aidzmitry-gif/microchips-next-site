# RB Lenovo official battery evidence — wave 166

Date: 2026-07-29. Site: `microchips-by`.

## Scope

The audit checked the 90 single-P/N Lenovo candidates from the current
2,188-card thin laptop cohort against Lenovo's official Battery Information
Finder workbook. The workbook is pinned by SHA-256
`bf8b37ece22e66ac59fcc6d3e938acbf79054fe9279b9e2575fb41e5897459a2`
and contains 2,480 battery rows.

## Result

| Result | Records |
| --- | ---: |
| Exact unique official P/N match | 21 |
| Not found in the official registry | 69 |
| Official voltage matches the legacy title | 8 |
| Official voltage conflicts with the legacy title | 13 |
| Official energy matches the legacy title | 2 |
| Official energy conflicts with the legacy title | 1 |
| Official energy absent from the title | 18 |

All 21 exact matches have official voltage and Wh data. The registry does not
prove the laptop compatibility claims or provide an exact reusable product
image. Derived mAh values remain audit-only and must not be presented as a
manufacturer-stated capacity.

## Decision

No database fields were changed. `manufacturer`, `mpn`, compatibility,
capacity and media remain behind a separate reviewed application gate.
The 13 voltage conflicts are explicit holds. The other eight exact-voltage
matches still require a source that proves the sold pack's compatibility and
image before the complete card can be promoted from `needs_primary_source`.

This is deliberate: the official regulatory registry proves the battery P/N
and electrical facts, but it is not evidence that every compatibility model
listed in a legacy reseller title is correct.

## Evidence files

- `docs/audits/sources/lenovo-battery-information-finder-2026-07-28.xlsx`;
- `docs/audits/generated/rb-lenovo-official-battery-evidence-wave166.csv`;
- `docs/audits/generated/rb-lenovo-official-battery-evidence-wave166.summary.json`.

## Verification

- evidence builder: 2 tests passed;
- selected Lenovo records: exactly 90;
- official registry rows: exactly 2,480;
- automatic database mutations: zero.
