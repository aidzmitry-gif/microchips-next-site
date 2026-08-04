# Wave216 no-repeat queue

Wave216 deterministically builds the next 500-card RB B2B research queue from the same 3,894-card incomplete, non-held research universe.
The authoritative processed set is exactly 3,000 unique cards: 2,500 from the prior aggregate register and the disjoint 359/115/26 Wave215 A/B/C ledgers.

## Guards

- Processed IDs are unique and all belong to the current incomplete, non-held B2B universe.
- Queue and source batch each contain 500 unique IDs, equal to one another, and have zero overlap with the processed register.
- Automotive and electronic-component exclusions are both zero for the selected research batch.
- All selected rows retain `safe_to_apply=false`; this planner makes no web request, database query, or database mutation.

## Counts

- Research universe: 3894.
- Remaining after processed exclusion: 894.
- Queue categories: {'seo:batteries-industrial': 4, 'seo:batteries-traction': 41, 'seo:chargers': 228, 'seo:power-systems': 84, 'seo:replacement-tools': 104, 'seo:warehouse-equipment': 39}.
- Byte-identical second rendering: True.
