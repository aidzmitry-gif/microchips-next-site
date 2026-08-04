# RB OEM missing-content evidence — wave 172

Date: 2026-07-29. Site: `microchips-by`.

## Scope and outcome

Forty-seven image-backed cards from the wave-170 missing-description queue
were checked against official manufacturer sources. Ten exact/model-core
identities passed the fail-closed content gate; 37 remain on hold. Together
with the seven industrial cards reviewed in wave 171, this prevents repeated
research on 54 of the 120 original rows.

| Decision | Cards |
| --- | ---: |
| Source-backed description applied | 10 |
| Identity/specification conflict | 18 |
| Exact product identity still missing | 19 |
| New external image imported | 0 |

## Applied cards

| External ID | Verified identity | Published facts |
| --- | --- | --- |
| `bitrix:11753` | ROBITON LiFe18650 | LiFePO4, 18650, 3.2 V, 1100 mAh, unprotected, dimensions and current/temperature limits from the [official product page](https://www.robiton.ru/product/13119/) |
| `bitrix:10573` | HP NZ375AA | Eight-cell battery and the 4510s/4515s/4710s series from the [official HP accessory document](https://h41201.www4.hp.com/AdLanding/img/cleansheet/program_special/6393_HP_EOFY_Business_Bonus_Eligible_Accesories_2014-08-05.pdf) |
| `bitrix:4774` | HP PH06 / BQ350AA | Six-cell battery and the explicitly listed notebook series from the same HP document |
| `bitrix:4776` | Dell J1KND | 11.1 V and 48 Wh from the [official Dell SDS](https://i.dell.com/sites/csdocuments/Legal_Docs/en/2019lgcsds.pdf) |
| `bitrix:4777` | Dell M5Y1K | 15.2 V and 40 Wh from the [official Dell SDS](https://si.cdn.dell.com/sites/csdocuments/Legal_Docs/en/lges_sds_2022.pdf) |
| `bitrix:4778` | Dell WDX0R | 11.4 V, 3500 mAh and 42 Wh from the [official Dell SDS](https://i.dell.com/sites/csdocuments/Legal_Docs/en/bat-smpsds20.pdf) |
| `bitrix:10747` | Lenovo L17M2PF0 | 7.5 V and 35 Wh from the [official Lenovo SDS](https://static.lenovo.com/ww/docs/regulatory/msds/SDS-Simplo-2001.pdf) |
| `bitrix:10833` | Lenovo 00HW022 | 11.25 V and 24 Wh from the [official Lenovo SDS](https://static.lenovo.com/ww/docs/regulatory/msds/SDS-IBH-00486.pdf) |
| `bitrix:10834` | Lenovo 00HW025 | 11.4 V and 24 Wh from the [official Lenovo SDS](https://static.lenovo.com/ww/docs/regulatory/msds/SDS-Simplo-2001.pdf) |
| `bitrix:4787` | Sony NP-BG1 / NP-FG1 | InfoLITHIUM G family and official NP-FG1 successor relationship from [Sony support](https://www.sony.com/electronics/support/compact-cameras-dsc-h-series/dsc-h1/articles/S1F0393) |

Legacy capacity and broad compatibility claims were deliberately removed from
the reader-facing name where the official source did not prove them.

## Holds: an official source contradicts or splits the legacy identity

- `bitrix:11754`: two official ROBITON 2600 mAh products have different
  terminals ([flat top](https://www.robiton.ru/product/13488/),
  [high top](https://www.robiton.ru/product/19771/)); the title does not say
  which one is offered.
- `bitrix:11755`: the closest official ROBITON Li3.0/18650 is rated 3.5 A,
  while the legacy title says 3.9 A
  ([manufacturer page](https://www.robiton.ru/product/13489/)).
- `bitrix:9428`, `bitrix:9556`, `bitrix:9853`, `bitrix:9879`,
  `bitrix:9904`: aftermarket Panasonic-compatible capacities conflict with
  official VBG/VBY specifications. Primary references:
  [Panasonic compatibility support](https://help.na.panasonic.com/answers/parts-and-accessories-what-battery-is-compatible-with-my-panasonic-camcorder/),
  [VBG manual](https://www.panasonic.com/content/dam/Panasonic/support_manual/Camcorder_Digital/English/vqt1y28.pdf),
  [VW-VBG6](https://eu.connect.panasonic.com/gb/en/broadcast-proav/accessories/vw-vbg6),
  [VW-VBY100](https://www.panasonic.com/es/consumer/camaras-y-videocamaras/accesorios-camaras/vw-vby100e-k.html).
- `bitrix:10498`, `bitrix:10501`: each Dell title combines multiple P/N and
  energy variants; Dell documents distinct 42/60/62 Wh packs
  ([7280 specification](https://www.dell.com/support/manuals/en-vc/latitude-12-7280-laptop/latitude_7280_ownersmanual/battery-specifications?guid=guid-cbd1c4e4-1129-42b2-828d-57e8382d236d&lang=en-us),
  [7290/7390/7490 specification](https://www.dell.com/support/manuals/en-us/latitude-14-7490-laptop/latitude_7290_7390_7490/battery-specifications?guid=guid-b834e5b3-da34-4e21-a8a9-c332961bc26c)).
- `bitrix:10646`: JC03 and JC04 are separate 31/41 Wh packs, and the official
  guide says 2.8 Ah rather than the legacy 2.2 Ah
  ([HP service guide](https://h10032.www1.hp.com/ctg/Manual/c05493256.pdf)).
- `bitrix:10260`: official ASUS documentation lists several C21N1347
  electrical variants and does not prove the legacy four-series compatibility
  claim ([ASUS certificate](https://dlcdnet.asus.com/pub/ASUS/nb/X555LI/Cert_KC_X555.pdf)).
- `bitrix:6954`: the official Nexus 7 guide says 4325 mAh, while the legacy
  title says 4200 mAh and gives no exact pack P/N
  ([ASUS guide](https://dlcdnet.asus.com/pub/ASUS/EeePAD/Nexus7/Nexus7Guidebook071212ENG.pdf)).
- `bitrix:10131`, `bitrix:10132`, `bitrix:10133`: Garmin publishes different
  replacement P/N compatibility by GPSMAP generation; the legacy titles mix
  those models and capacities
  ([010-10517-00 support](https://support.garmin.com/de-DE/?partNumber=010-10517-00&tab=topics),
  [Garmin compatibility notice](https://support.garmin.com/en-AU/marine/faq/PTO2XLBWE24MiraEZQWaS9/)).
- `bitrix:10965`: the title mixes Samsung and Motorola identities.
- `bitrix:16607`: the title joins AB463651BE and AB463651BU, while the official
  Samsung page proves only the former identity and no shared specification
  ([Samsung support](https://www.samsung.com/uk/support/model/AB463651BECSTD/)).
- `bitrix:4769`: “Galaxy Tab S7” is not a battery identity; Samsung documents
  different battery sizes for S7 and S7+
  ([Samsung product specification](https://www.samsung.com/sg/tablets/galaxy-tab-s7/)).

## Holds: exact offered pack is still unproved

The following records have only a device family, aftermarket code or
incomplete replacement identity and therefore remain `needs_primary_source`:

- HP: `bitrix:10653`, `bitrix:10654`, `bitrix:10690`, `bitrix:10691`,
  `bitrix:4773`;
- ASUS: `bitrix:10035`, `bitrix:10282`, `bitrix:15757`, `bitrix:4780`,
  `bitrix:4781`;
- Lenovo: `bitrix:4744`;
- Garmin/Starnovo: `bitrix:4755`;
- Samsung: `bitrix:7113`, `bitrix:7114`;
- Sony/CameronSino: `bitrix:11982`, `bitrix:4964`, `bitrix:9454`,
  `bitrix:16839`;
- Atlas Battery: `bitrix:25928`.

## Image decision

All 47 rows retain only their existing company-owned Bitrix preview image.
No OEM image was copied: none of the reviewed sources supplied both exact
offered-pack identity and explicit commercial reuse permission. Manufacturer
legal terms remain restrictive, including [Lenovo](https://www.lenovo.com/ph/en/legal/),
[Samsung](https://www.samsung.com/us/common/legal/),
[Sony](https://developer.sony.com/terms-of-use) and
[Garmin](https://www.garmin.com/en-XD/legal/terms-of-use/).

## Applied manifests

- `docs/imports/rb-source-backed-description-drafts-robiton-life18650-wave172-2026-07-29.json`;
- `docs/imports/rb-source-backed-description-drafts-oem-exact-wave172-2026-07-29.json`.

