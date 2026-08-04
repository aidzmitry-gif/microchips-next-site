# RB Wave217-B — official device-source gate

Wave217-B processes exactly 56 records from the Wave216 batch: ROBITON 45,
Panasonic 10, and EnerSys 1. The scope contains battery chargers, power
supplies and one stationary battery; it contains no automotive item or
electronic component.

Two identities have exact primary-source evidence: `bitrix:3411` ROBITON
SmartDisplay 1000 and `bitrix:742` EnerSys Cyclon X Cell. Both are nevertheless
held by the live collision guard: the current 1C inventory already has the
same respective manufacturer/model identities. The exact-safe manifest is
therefore empty. The other 54 rows are held because no SHA-pinned official
exact-model page or datasheet was used for them.

Laravel runs only without `--apply`; its receipt confirms the expected empty
manifest fail-closed result and zero database mutations.

Twenty-nine ROBITON entries explicitly called `Блок питания` are not treated
as chargers merely because their legacy category is `seo:chargers`. They form
a strict three-column move manifest from `seo:chargers` to the existing
`seo:power-supplies` leaf. ImportRun 945 applied all 29 moves and updated their
29 noindex routes; ImportRun 946 proved idempotence with 29 already moved.
Publication flags changed: 0. The post-apply SEO audit reports 16,853 URLs,
97 redirects and 0 blockers. Rows without that explicit title stay out of the
manifest. The receipt is
`docs/audits/generated/wave217b-robiton-category-application-receipt.json`.
