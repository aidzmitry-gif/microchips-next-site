# Wave215-A power systems

Wave215-A classifies exactly 359 `seo:power-systems` records from the SHA-pinned Wave214 batch.
It keeps power equipment distinct from batteries: all records are UPS systems or AC/DC/DC/DC power converters; none is an electronic component.

## Scope and no-repeat guards

- Source clusters: {'APC': 36, 'unresolved_industrial_cell': 5, 'unresolved_other': 318}
- Factual types: {'ac_dc_power_supply': 12, 'dc_dc_power_converter': 33, 'ups_system': 314}
- Processed2500 and all prior Wave evidence IDs have zero overlap with this batch.
- The full canonical registry, in-batch duplicate index, and read-only live-product identity check were run for every row.

## Evidence policy

- Pinned APC Wave199 primary evidence exact matches: 0 of 36 APC UPS rows.
- Wave199 is an APC replacement-battery-cartridge dataset, so its source bytes are not reused for a different APC ID, title, or title-derived UPS model.
- Large unresolved UPS and converter families are routed to manufacturer-first-party batch research. Title labels remain candidates, not confirmed OEM identities.
- The exact-safe manifest is empty; the Laravel command was executed without `--apply` and failed closed on its required non-empty product list.

## Title-derived family routing

- Families: {'5E': 3, '5P': 5, '5PX': 2, '5S': 4, '5SC': 3, '600': 1, '9130': 1, '9E2000I': 1, '9SX': 2, '9SX3000I': 1, '9SX3000IR': 1, 'Argus': 3, 'BETA': 2, 'BS': 3, 'BU': 3, 'Back': 25, 'Back UPS': 4, 'Back UPS Pro BR': 2, 'Balder': 5, 'CMU': 4, 'CMU-SP': 2, 'CMUOA': 1, 'CMUS': 2, 'CPS': 5, 'Cadu': 1, 'Control HPS20-0312': 1, 'Control HPS20-0312N': 1, 'Control HPS20-0612': 1, 'Control HPS20-0612N': 1, 'Control HPS20-1012': 1, 'Control HPS20-1012N': 1, 'Control HPS30-1512': 1, 'Control HPS30-2012': 1, 'Control HPS30-3024': 1, 'Control HS20-1012P': 1, 'Control HS20-2024P': 1, 'Control HS20-3024P': 1, 'Control HS20-4048P': 1, 'Control HS20-5048P': 1, 'Control HS20-5548': 1, 'DCW': 2, 'DCWN': 5, 'DDR': 20, 'DP': 1, 'DPV': 1, 'Desktop EG-UPS-3SDT1000-01': 1, 'Desktop EG-UPS-3SDT600-01': 1, 'Desktop EG-UPS-3SDT800-01': 1, 'E-Power': 3, 'E-Power PSW-H16': 1, 'E-Power SW910Pro-T': 1, 'EG-UPS-PS': 3, 'Easy UPS BV': 4, 'Easy UPS BVX': 4, 'Easy UPS On-Line SRV': 2, 'Easy UPS On-Line SRV RM': 1, 'Expert UDC92010H': 1, 'Expert UDC9206H': 1, 'GAMMA': 1, 'Gamma': 7, 'Garun': 4, 'Horus': 2, 'INF': 3, 'Imperial': 2, 'Infinity': 1, 'Innova': 11, 'Innova G2': 4, 'KR': 1, 'KU': 3, 'Keen': 5, 'King': 3, 'MY': 4, 'Macan': 8, 'Online OL1000': 1, 'Online OL1500': 1, 'Online OL2000': 1, 'Optima': 1, 'PR': 2, 'PSW-H': 1, 'PSW-HW': 1, 'Power': 4, 'Power A1000': 1, 'Power A2000': 1, 'Power A850': 1, 'PowerExpert': 2, 'Powerware': 1, 'Pro': 2, 'Professional': 3, 'Professional PR3000': 1, 'RPT': 4, 'RPT-600AP SE2': 1, 'RT': 2, 'Raptor': 10, 'Renton': 2, 'SIGMA': 1, 'SMART': 1, 'SPD': 1, 'SPIDER': 1, 'SSW': 1, 'Sentinel': 1, 'ServerRM': 1, 'SinePower': 3, 'Smart': 17, 'Smart UPS 750VA': 1, 'Smart UPS SC': 1, 'Smart UPS SRT': 1, 'Smart-UPS': 8, 'Smart-UPS C': 4, 'Smart-UPS RT': 1, 'Smart-UPS SRT': 1, 'Smart-UPS X': 2, 'Soter': 1, 'SpecialPro': 3, 'Spider': 6, 'UT': 5, 'UTC': 5, 'UTI': 2, 'VGD-II': 2, 'Vanguard': 4, 'WOW': 5, 'Гарант': 3, 'МПА': 4, 'МПВ': 2, 'МПС': 12, 'Про': 1, 'СПИ ИБП-11-002-006-УХЛ4': 1, 'СПИ ИБП-11-003-006-УХЛ4': 1}

Laravel dry-run exit: 1 (expected fail-closed); database mutations: 0.
