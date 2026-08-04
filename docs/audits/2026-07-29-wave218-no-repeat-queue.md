# Wave218 final no-repeat research queue

Wave218 extends the 3,000-row Wave216 register with the disjoint Wave217 A/B/C ledgers (395/56/49), producing exactly 3,500 unique processed IDs. The fixed 3,894-card incomplete non-held B2B research universe therefore has 394 remaining records; the requested limit of 500 does not pad or repeat them.

The priority queue and source batch each contain the same 394 IDs, have zero processed overlap, exclude automotive and electronic-component scope, and retain `safe_to_apply=false`. Two local renderings are byte-identical. No web, database, or application mutation occurs.
