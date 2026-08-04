# Wave213-A medical replacement-battery triage

Wave213-A deterministically processes all 274 `unresolved_replacement` rows from Wave212. All remain in the B2B medical replacement category; none is treated as automotive or electronic-component scope. The triage extracts a device OEM/model, device family, battery-pack form, explicit pack part number where present, voltage and capacity declared by the legacy title.

It reports device-family variant groups plus exact-name and parsed device/pack collision candidates in the full canonical registry and current PostgreSQL. PostgreSQL is read only and `apply_records=0`. No web request was made.

The exact-safe manifest is deliberately empty. A medical-device manual that merely says a pack is compatible cannot establish a product identity. Promotion requires a SHA-pinned first-party device OEM accessory/service manual or battery-pack OEM source that explicitly proves the exact sellable pack and its device compatibility.
