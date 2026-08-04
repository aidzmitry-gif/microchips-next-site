# Wave241-C description/image no-repeat reconciliation

The Wave240 queue has exactly 502 UPS-battery rows with neither an applied description nor a verified published image. All 458 blank-manufacturer rows match a prior reviewed identity HOLD by exact external ID and normalized exact title; they are skipped rather than researched again.

The remaining 44 rows already have an exact manufacturer/MPN and hash-pinned manufacturer-primary identity evidence: EnerSys 15, Sonnenschein 8, MNB 8, APC 5, Panasonic 4 and Ventura 4. No prior description manifest matches any of them by external ID, normalized manufacturer+MPN or exact title, so no pre-existing description can be safely replayed. They are isolated as new description work; image recovery remains a separate rights and visible-identity review.

No database query, database mutation, network request or apply action is performed.
