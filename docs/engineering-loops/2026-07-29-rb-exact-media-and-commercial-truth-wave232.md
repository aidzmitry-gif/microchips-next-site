# Wave232 — точные B2B-изображения, описания EnerSys и коммерческая достоверность

Дата: 2026-07-29  
Профиль: `microchips-by`

## Результат

- Из 89 новых company-owned Bitrix media-кандидатов 47 были сразу оставлены HOLD из-за повторного использования одного файла между разными товарами.
- Оставшиеся 42 изображения прошли OCR, визуальную проверку и сопоставление с официальными источниками:
  - APC/Schneider: 28 HOLD — точная модель на изображении не читается;
  - EnerSys/CYCLON: 1 PASS (`bitrix:24582`, `0859-0016`) и 9 HOLD;
  - IPPON: 3 HOLD — видны бренд и корпус, но не точная модель;
  - EnerSys PowerSafe: 1 PASS (`bitrix:26048`, `12V70`).
- Два PASS-изображения являются собственными файлами из Bitrix backup. Официальные PDF использованы только для подтверждения идентичности, не как разрешение копировать изображения производителя.
- Обе карточки получили manufacturer-primary описания и технические характеристики из закреплённых официальных PDF EnerSys.
- Цена, наличие, URL, индексируемость и региональная публикация не изменялись. Обе карточки остались `availability=on_request`, `price=NULL`.

## Коммерческие данные

Read-only аудит подтвердил:

- карточек РБ в `site_products`: 24 298; опубликовано: 16 816;
- числовая цена с текущим provenance: 57, из них 34 у опубликованных карточек;
- все 24 298 карточек имеют честный статус `on_request`; `in_stock` не заявлен ни для одной;
- в текущей 1С-номенклатуре 9 123 товарные строки, но 0 положительных цен, 0 валют и 0 типов цены;
- правило `1С × 2` реализовано и проверяет источник, валюту и дату, но текущая выгрузка не содержит данных, к которым его можно применить;
- цена не считается доказательством складского остатка; без отдельного provenance наличие `in_stock` и `Offer` не создаются.

## Изменение готовности каталога

| Метрика | До | После | Изменение |
|---|---:|---:|---:|
| Content-complete | 339 | 341 | +2 |
| Strict content ready | 160 | 162 | +2 |
| Очередь до фиксированной цели 10% | 1 303 | 1 301 | −2 |

Общая подтверждённая готовность проекта остаётся **60%**: прирост каталога измерим, но он не закрывает остальные региональные, инфраструктурные и пострелизные гейты.

## Аудиторские записи

- media promotion dry-run/apply: по одному точному media в Wave232-E и Wave232-F, всего 2;
- ImportRun `1002`: fail-closed проверка отклонила exact-описание `12V70`, потому что старое название содержало слова после MPN;
- manifest исправлен на bounded `model_core` для уже существующего MPN `12V70`, без смены идентичности;
- ImportRun `1003–1004`: description stage dry-run/apply, 2 записи;
- ImportRun `1005–1006`: description apply dry-run/apply, 2 записи;
- post-apply: у обеих карточек 1 verified published media и 1 applied manufacturer-primary description.

## Верификация

- Python builders: 7 тестов успешно;
- Python compilation: 4 builder-файла успешно;
- SEO audit: 16 853 URL, 97 redirect, 0 blocker;
- `scripts/verify-rb-prototype.ps1`: 4/4 HTML-прототипа успешно;
- коммерческий audit: 0 цен без provenance, 0 value mismatch, 0 duplicate current evidence;
- PHPUnit в production Docker image не запускался: production-образ намеренно собран с `composer install --no-dev`, поэтому PHPUnit отсутствует. Новая логика PHP в этом цикле не добавлялась.

## Основные артефакты

- `docs/imports/rb-reviewed-legacy-preview-media-wave232e-2026-07-29.json`;
- `docs/imports/rb-legacy-exact-preview-media-wave232f-2026-07-29.json`;
- `docs/imports/rb-source-backed-descriptions-wave232g-2026-07-29.json`;
- `docs/audits/generated/rb-full-content-readiness-wave232-after.csv`;
- `docs/audits/generated/rb-enrichment-queue-wave232.csv`;
- `docs/audits/generated/rb-commercial-data-wave215c-summary.json`.

Коммит и push не выполнялись.
