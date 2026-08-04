# RB Wave215-B — traction battery primary-source gate

Input is exactly the 115 `seo:batteries-traction` records in
`rb-b2b-next-source-batch-wave214.csv`: Minamoto 5, Sonnenschein 15, Yuasa 2,
unresolved_other 78, and unresolved_replacement 15.

The output is fail-closed.  The pinned official GS Yuasa catalogue proves the
two exact DCB models, so the OEM identity manifest contains only
`bitrix:24373` (`DCB145-6`) and `bitrix:24374` (`DCB105-6`).  It is strictly
identity evidence: legacy AGM/capacity values are not copied as verified facts.

All 15 `unresolved_replacement` records name batteries, but their boat/marine
wording is recorded as device-compatibility context only; it does not establish
an offered replacement battery identity.  Minamoto and Sonnenschein remain
holds: no locally SHA-pinned official exact-model snapshot was available.  No
automotive-starter or electronic-component record is in this wave.

The Laravel command is run without `--apply`.  The receipt records two
validated identities, no commercial or publication changes, and zero database
mutations.
