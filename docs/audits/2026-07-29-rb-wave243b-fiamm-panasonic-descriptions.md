# Wave243B: FIAMM / Panasonic missing-description evidence

Дата проверки: 2026-07-29  
Режим: evidence-only, без `--apply`, без публикации

## Замороженный scope

Источник: `docs/audits/generated/rb-enrichment-queue-wave242.csv`, SHA-256
`8d7f4435b25327d3f6a3b9015d0b535cf64f3aad1342378fc165abc4be1e7867`.

- 88 Bitrix-карточек без applied description и без заполненных identity fields;
- FIAMM: 56;
- Panasonic: 32.

## Duplicate gate

Перед проверкой источников закреплён read-only снимок 148 активных/канонических
FIAMM/Panasonic товаров: `canonical-products-snapshot.csv`, SHA-256
`cd60393c567d6ee20d13a4540c38bffb0d584769e6bf9ee6713930e47c146662`.

Найдены 4 exact Bitrix -> 1C дубля; они не включены ни в identity-, ни в
description-manifest:

| Bitrix | MPN | Канонический external_id | Решение |
|---|---|---|---|
| `bitrix:3266` | `12FGH36` | `ФР-00002108` | `HOLD_LEGACY_DUPLICATE` |
| `bitrix:1511` | `4SLA150` | `КА-00003136` | `HOLD_LEGACY_DUPLICATE` |
| `bitrix:1488` | `FG21202` | `ФР-00001439` | `HOLD_LEGACY_DUPLICATE` |
| `bitrix:1542` | `FG21803` | `ФР-00001513` | `HOLD_LEGACY_DUPLICATE` |

Похожий канонический Panasonic `LC-R127R2PG1` не приравнивался к
`LC-R127R2PG`: suffix сохранён как часть exact MPN.

## Новые manufacturer-primary источники

Использованы 7 новых HTTPS URL на manufacturer-primary хостах:

- FIAMM: 2 точных индивидуальных PDF (`FG27004`, `FG2A007`);
- Panasonic: 4 индивидуальных PDF (`LC-P0612P`, `LC-R0612P/P1`,
  `LC-R063R4P`, `LC-R067R2P/P1`);
- Panasonic: 1 официальный VRLA catalogue PDF с точной таблицей membership.

Builder проверяет каждый snapshot SHA, точное вхождение модели/документированное
slash-membership и fail-closed сканирует прежние audit/import artefacts. Итог:

- совпадений URL с прошлыми waves: 0;
- совпадений snapshot SHA с прошлыми source directories: 0;
- источников dealer/marketplace: 0.

PDF были извлечены через `pdfplumber`, первые страницы всех семи документов и
страница таблицы Panasonic были отрендерены через Poppler и визуально проверены.
Модель, номиналы и membership читаемы, clipping/перекрытий в доказательных
областях нет.

## Решения

| Решение | Количество |
|---|---:|
| PASS exact individual datasheet | 6 |
| PASS exact datasheet membership | 2 |
| PASS exact catalogue membership | 5 |
| HOLD exact legacy duplicate | 4 |
| HOLD без нового exact manufacturer-primary evidence | 71 |
| **Всего** | **88** |

В manifests вошли только 13 PASS. `LC-R121R3PG` оставлен в HOLD: официальный
catalogue содержит `LC-121R3PG`, а не exact `LC-R121R3PG`. Обобщение по серии и
автоматическое исправление MPN не выполнялись.

## Артефакты

- `scripts/acquire-rb-wave243b-fiamm-panasonic-primary.py`;
- `scripts/build-rb-wave243b-fiamm-panasonic-descriptions.py`;
- `scripts/tests/test_build_rb_wave243b_fiamm_panasonic_descriptions.py`;
- `docs/audits/sources/wave243b-fiamm-panasonic/`;
- `docs/audits/generated/rb-wave243b-fiamm-panasonic-description-ledger.csv`;
- `docs/audits/generated/rb-wave243b-fiamm-panasonic-description.summary.json`;
- `docs/imports/rb-verified-oem-identities-wave243b-fiamm-panasonic-2026-07-29.json`;
- `docs/imports/rb-source-backed-descriptions-wave243b-fiamm-panasonic-2026-07-29.json`.

## Верификация

`python -m pytest -p no:cacheprovider scripts/tests/test_build_rb_wave243b_fiamm_panasonic_descriptions.py -q`

Результат: `4 passed`.

Laravel без `--apply`:

- `catalog:apply-verified-oem-identities`: `mode=dry_run`, 13 records,
  manifest SHA-256 `72348c91414d3c0dc3da9ebee0672a523680cc15d84c2d557cf8c9daf021e7f4`,
  commercial/publication changes = 0;
- `content:stage-source-backed-description-drafts`: run 1070,
  `0 created, 0 refreshed, 13 unchanged; none were published`.

Ни одна команда с `--apply` не запускалась.
