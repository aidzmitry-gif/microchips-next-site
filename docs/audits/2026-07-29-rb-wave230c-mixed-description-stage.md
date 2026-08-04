# Wave230-C: remaining mixed manufacturer-primary descriptions

This package covers exactly 28 frozen Wave230 verified-media targets: Ventura (7), Casil (5), ROBITON (5), B.B. Battery (4), Delta/DELTA (6) and Panasonic (1). Each row is tied to the Wave229 media ID, SHA-256 and `visible_exact_mpn` proof before staging evidence is evaluated.

Only existing SHA-pinned manufacturer-primary evidence is reused: Ventura/Panasonic catalogue rows, Casil/ROBITON product pages, B.B. Battery catalogues and Delta product pages. Each snapshot is rehashed and must contain the exact MPN and a conservative technology token.

The strict raw `nameEndsWith(MPN)` contract fails for all 28 catalogue names because each retains a technical suffix. Therefore every stage row is bounded manufacturer-primary `model_core`, with no exact-only `mpn` or display-name field. The generated manifest is stage-only (`--refresh-existing --refresh-applied` after review); this builder does not execute it or apply database, publication, commercial, media, URL or identity changes.
