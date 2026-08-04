# Wave215-C medical B2B and EnerSys UPS evidence

Wave215-C is the disjoint 26-row C lane of Wave214: 24 medical replacement records and two EnerSys UPS records. The medical records remain in `seo:replacement-medical`; their extracted device OEM/model and any legacy pack labels are not represented as sellable-pack OEM identities.

The SHA-pinned primary EnerSys Cyclon catalogue explicitly contains BC Cell / 0820-0004 and E Cell / 0850-0004. The exact series in the legacy titles are the bounded product identities; the catalogue part numbers are retained as source evidence and are not substituted into the titles.

Registry and live PostgreSQL checks are read only. The two-row exact-safe manifest was passed to Laravel without `--apply`; a second read-only query confirmed no identity field changed.
