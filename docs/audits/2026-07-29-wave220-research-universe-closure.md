# Wave220 fixed research-universe closure

Wave220 extends the 3,500-ID Wave218 register with the three disjoint Wave219 ledgers: A 277, B 60 and C 57. The resulting historical research ledger has 3,894 unique IDs and exactly equals the fixed Wave172 incomplete, non-held B2B research universe.

Wave221 is a live-state reconciliation, not the historical universe. Its B2B footprint contains 3,888 of the 3,894 historical IDs. The exact six absent IDs are all accounted for by pinned duplicate-collapse manifests, with each canonical survivor still present in the Wave221 B2B state and each retired legacy path recorded by the authoritative manifest. Wave221 also contains live B2B rows outside this historical ledger; they are deliberately not silently folded into the historical closure.

The header-only queue remains a verification of the pinned historical Wave172 universe, not a claim about all Wave221 live B2B products. No web request, database query, database mutation, or apply action occurs. Two local renderings are byte-identical.
