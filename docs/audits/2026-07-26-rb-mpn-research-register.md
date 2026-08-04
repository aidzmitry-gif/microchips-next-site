# RB: реестр внешних доказательств MPN для Gate 0

Дата исследования: 2026-07-26. Реестр не публикует товар и не переносит
описания, фотографии или цены с чужих сайтов. Он фиксирует только evidence
модели и минимальные параметры для решения review.

Статусы: **ready** — точная модель и бренд подтверждены источником; **hold**
— доказательство не первичное, модель неоднозначна или бренд не доказан.
Каждое `ready`-решение всё равно проходит duplicate guard в Filament.

| Candidate | Bitrix ↔ 1С | MPN для review | Evidence | Статус |
| ---: | --- | --- | --- | --- |
| 2 | Delta DT 401 | `DT401` | [Delta DT catalogue](https://delta-batt.com/series/dt/) | ready |
| 4 | Delta DTM 6012 | `DTM6012` | [Delta DTM catalogue](https://delta-batt.com/series/dtm/) | ready |
| 5 | Casil CA 1213 | `CA1213` | [Casil manufacturer catalogue](https://www.electro51.ru/assets/files/catalogs/CASIL-Battery-Product-Catalogue.pdf) | ready |
| 8 | Delta DT 12100 | `DT12100` | [Delta product page](https://www.delta-battery.ru/catalog/dt/delta-dt-12100/) | ready |
| 9 | FIAMM 6SLA100 | `6SLA100` | [FIAMM branded PDF](https://www.h-energy.ru/wa-data/public/site/manuals/akb/fiamm/fiamm_6sla100-datasheetENG.pdf) | ready |
| 11 | Ventura VG 12-100 | `VG12-100` | [Ventura product page](https://ventura-battery.ru/catalog/ventura-vg/vg-12-100/) | ready |
| 12 | Ventura GP 6-12 | `GP6-12` | [Ventura official documentation](https://ventura-battery.ru/podderzhka/) | ready |
| 13 | FIAMM 6SLA125 | `6SLA125` | [FIAMM branded PDF](https://www.cogenient.com/mfc-refdocs/Fiamm/SLA/6SLA125.pdf) | ready |
| 16 | FIAMM FG21202 | `FG21202` | [FIAMM product sheet](https://actec.dk/media/documents/55A6358C73AF.pdf) | ready |
| 17 | Delta DTM 12150L | `DTM12150L` | [manufacturer-branded PDF](https://asterion-batt.com.tr/upload/iblock/5e6/5e680316f5321103e7282455af64af4b.pdf) | ready |
| 18 | FIAMM 4SLA150 | `4SLA150` | [FIAMM datasheet](https://www.cogenient.com/mfc-refdocs/Fiamm/SLA/4SLA150.pdf) | ready |
| 19 | Ventura FT 12-150 | `FT12-150` | [Ventura product page](https://ventura-battery.ru/catalog/ventura-ft/ft-12-150/) | ready |
| 20 | Ventura GPL 12-150 | `GPL12-150` | [Ventura product page](https://ventura-battery.ru/catalog/ventura-gpl/gpl-12-150/) | ready |
| 21 | Delta DTM 1215 | `DTM1215` | [Delta product page](https://www.delta-battery.ru/catalog/dtm/delta-dtm-1215/) | ready |
| 23 | FIAMM 12FIT180 | `12FIT180` | [FIAMM product page](https://fiamm.ru/equipment/FIT-series/12FIT180/) | ready |
| 24 | FIAMM FG21803 | `FG21803` | [FIAMM PDF](https://www.fiamm.co/catalog/FG21803.pdf) | ready |
| 27 | Delta DT 6028 | `DT6028` | [Delta product page](https://www.delta-battery.ru/catalog/dt/delta-dt-6028/) | ready |
| 28 | Ventura GPL 12-200 | `GPL12-200` | [Ventura PDF](https://ventura-battery.ru/upload/documents/gpl/GPL_12-200.pdf) | ready |
| 29 | Ventura VG 12-200 | `VG12-200` | [Ventura datasheet](https://ventura-battery.ru/upload/documents/vg/VG_12-200.pdf) | ready |
| 31 | Ventura HRL12155W | `HRL12155W` | [Ventura catalogue](https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf) | ready |
| 32 | B.B. Battery HR33-12 | `HR33-12` | [official B.B. Battery series page](https://www.bb-bat.com/en/HR.html) | ready |
| 34 | B.B. Battery BP5-12 | `BP5-12` | [official B.B. Battery catalogue](https://www.bb-batte.com/?lang=en) | ready |
| 38 | Ventura GP 12-7.2 | `GP12-7.2` | [Ventura datasheet](https://ventura-battery.ru/upload/documents/gp/GP_12-7.2.pdf) | ready |
| 39 | Ventura GPL 12-75 | `GPL12-75` | [Ventura datasheet](https://ventura-battery.ru/upload/documents/gpl/GPL_12-75.pdf) | ready |
| 43 | Sonnenschein A502/10S | `A502/10S` | [Exide official page](https://www.exidegroup.com/eu/en/document/performance-durability-data-0) | ready |
| 45 | Sprinter XP12V3400 | `XP12V3400` | [Exide operating instructions](https://www.exidegroup.com/hk/sites/default/files/2024-11/operating-instructions-vrla-batteries_11.2024_0.pdf) | ready |
| 48 | Восток PRO СК-1218 | `СК-1218` | [Восток PRO catalogue](https://www.elec.ru/files/2023/06/19/Katalog-Vostok-PRO.pdf) | ready |

Итог: **27 ready / 0 hold** для исходного RB-пакета из 50 кандидатов. Все решения
прошли duplicate guard, staged в отдельных delta-run и созданы только как
непубличные RB drafts. Это закрывает identity-срез Gate 0, но не разрешает
публикацию товарных URL без категории, коммерческих фактов и SEO release gate.
