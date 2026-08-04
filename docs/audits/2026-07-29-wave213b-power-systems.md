# Wave213-B power systems evidence

Checked 221 `unresolved_other` rows from Wave212, all in `seo:power-systems`.
Every row is an AC/DC power supply (`power_system`); UPS, inverter, battery and accessory rows are all zero.
No battery capacity, chemistry, or replacement-pack claim was attached to any power-supply device.

## Evidence and routing

Five SHA-pinned official Mean Well datasheets cover the verified Mean Well/IRM family routes. Exact-safe identities: 13.
ZGQNYI-labelled rows remain a manufacturer-identity hold: familiar Mean Well-like model strings are not treated as Mean Well products.
The unbranded БПС30/БПЛ30/ММС5/МПС60 rows remain manufacturer-unresolved pending a first-party catalogue or maker confirmation.

## Counts

- Partitions: {'conflict': 1, 'exact_safe': 13, 'manufacturer_hold': 207}
- Families: {'DR-30': 4, 'DR-45': 4, 'DR-60': 4, 'EDR-120': 3, 'EDR-75': 3, 'ELP-75': 4, 'EPP-100': 4, 'EPS-25': 5, 'IRM-01': 1, 'IRM-02': 1, 'IRM-03': 2, 'IRM-05': 3, 'IRM-10': 3, 'IRM-20': 1, 'LRS-100': 4, 'LRS-150': 4, 'LRS-35': 4, 'LRS-350': 3, 'LRS-50': 4, 'LRS-75': 4, 'MDR-10': 4, 'MDR-20': 4, 'MDR-40': 4, 'MDR-60': 3, 'MS-100': 5, 'MS-1000': 4, 'MS-120': 5, 'MS-15': 3, 'MS-150': 5, 'MS-25': 3, 'MS-250': 5, 'MS-35': 3, 'MS-50': 1, 'MS-500': 4, 'MS-60': 4, 'MS-600': 4, 'MS-75': 2, 'MS-800': 3, 'NDR-240': 2, 'RPS-200': 4, 'RPS-65': 5, 'S-100': 5, 'S-1000': 2, 'S-120': 5, 'S-15': 4, 'S-200': 6, 'S-25': 4, 'S-250': 4, 'S-35': 4, 'S-350': 1, 'S-350-450': 3, 'S-50': 4, 'S-500-600': 5, 'S-60': 4, 'S-75': 2, 'S-800': 2, 'БПЛ30С': 1, 'БПС30А': 1, 'БПС30Б': 1, 'БПС30В': 1, 'БПС30Г': 1, 'БПС30Д': 1, 'БПС30Е': 1, 'БПС30И': 1, 'БПС30Н': 1, 'БПС30У': 1, 'БПС30Ю': 1, 'ММС5А': 1, 'ММС5Б': 1, 'ММС5В': 1, 'ММС5Г': 1, 'ММС5Д': 1, 'ММС5Е': 1, 'ММС5И': 1, 'ММС5Н': 1, 'ММС5С': 1, 'ММС5У': 1, 'ММС5Ю': 1, 'МПС60-3.3': 1, 'МПС60A': 1}
- Source routes: {'Mean_Well_SHA_pinned_official_datasheet': 14, 'ZGQNYI_first_party_product_page_or_manufacturer_directory_required': 164, 'manufacturer_identity_resolution_required_before_primary_research': 19, 'manufacturer_resolution_and_first_party_catalogue_required': 24}
- Full registry and current live DB collision checks are recorded in the generated ledger; the Laravel command was run without `--apply`.

## Application verification

- Independent focused tests: **4 passed**.
- Independent Laravel dry-run: 13 records, exit 0.
- Import run **936** filled all 13 exact-safe Mean Well identities.
- Idempotence rerun: `0 filled / 13 unchanged`.
- Commercial and publication fields changed: **0**.
- Final SEO audit: **16,853 URLs, 97 redirects, 0 blockers**.

## Pinned primary sources

- ELP: https://www.meanwell.com/Upload/PDF/ELP-75/ELP-75-SPEC.PDF — `25fe3088b83f753ca70f02814e19ee890b10f3133752eb919cc450a57031dd29`
- EPP: https://www.meanwell.com/Upload/PDF/EPP-100/EPP-100-SPEC.PDF — `6f5c4e0bf5a3531d0fd30007ec77ebdcbf877adfb074bb5575b9f12c30ca0022`
- EPS: https://www.meanwell.com/Upload/PDF/EPS-25/EPS-25-SPEC.PDF — `76ed83c0682b7064b85fb3deb9384ddd9aef1f96f854c10cb3ae01acb8531a7a`
- IRM: https://www.meanwell.com/Upload/PDF/IRM-01/IRM-01-SPEC.PDF — `4cae2c13412f3c56634f6a4bbf8d48c3c7ab86d875905877dfe9036a2834963d`
- RPS: https://www.meanwell.com/Upload/PDF/RPS-200/RPS-200-SPEC.PDF — `0e9d188e196d6317d38c9b63205ec57a917b89db339ff49cc8cc6a03a60b9037`
