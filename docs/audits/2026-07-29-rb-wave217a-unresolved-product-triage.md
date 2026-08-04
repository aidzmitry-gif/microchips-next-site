# Wave217-A unresolved product triage

Wave217-A classifies exactly 395 `unresolved_other` rows from Wave216 into saleable B2B product types and title-bounded model/family candidates.
No unpinned or lookalike source is converted into an OEM identity; all records remain held for exact manufacturer-primary research.

## Scope

- Product types: {'battery_charger': 165, 'dc_dc_power_converter': 26, 'electric_warehouse_stacker': 38, 'laboratory_power_supply': 46, 'manual_pallet_truck': 1, 'power_supply_adapter': 7, 'power_tool_battery_charger_kit': 24, 'power_tool_replacement_battery': 74, 'traction_battery': 2, 'ups_system': 12}
- Categories: {'seo:batteries-traction': 2, 'seo:chargers': 172, 'seo:power-systems': 84, 'seo:replacement-tools': 98, 'seo:warehouse-equipment': 39}
- Automotive rows: 0; electronic-component rows: 0; processed3000 overlap: 0; prior-evidence overlap: 0.

## Source and application policy

- Title brand/model/family values are routing candidates only; a primary product page or datasheet must match the exact current ID, title and bounded model before an identity can be applied.
- The exact-safe manifest is empty. Laravel was run without `--apply` and rejected its required non-empty product list; database mutations remain zero.
- Registry and live-product collision guards are recorded for every candidate.

Laravel dry-run exit: 1 (expected fail-closed); database mutations: 0.
