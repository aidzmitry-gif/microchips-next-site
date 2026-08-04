# RB Panasonic Wave 200 — официальный model-core пакет

Дата: 2026-07-29  
Регион: Беларусь (`microchips-by`, `ru-BY`)  
Статус: применён и верифицирован

## Результат

- Исходная очередь: **153** карточки Panasonic CR/BR из Bitrix-среза.
- Точное официальное доказательство найдено для **125** карточек по **28** ограниченным model core.
- **28** неоднозначных карточек оставлены в hold; догадки к ним не применялись.
- Для 125 карточек добавлены официальные технические характеристики и описания.
- Названия, SKU, MPN, статус товара, цена, валюта, наличие, публикация и SEO-индексация не изменены.
- Неподтверждённые цена, остаток, изображение и гарантия не создавались.

## Источники

Использованы два сохранённых документа Panasonic Energy:

- `docs/audits/sources/panasonic-wave200/Introduction_coin_primary_lithium_EN.pdf`  
  SHA-256: `1ce9b9fa72a6263f34cf2390726ddb009759c04303c1d3f39bc981473af5f343`
- `docs/audits/sources/panasonic-wave200/Introduction_cylindrical_primary_lithium_EN.pdf`  
  SHA-256: `116c40368f6ee67f5c7842c3b6d3968089c5a979c40fcb0275b303f86f1705ca`

Полная partition:

- evidence: `docs/audits/generated/rb-panasonic-wave200-official-evidence.csv` — 125;
- holds: `docs/imports/rb-panasonic-wave200-model-core-holds.csv` — 28;
- всего: 153, потерь между ветками нет.

## Применение

Манифест:

- `docs/imports/rb-source-backed-description-drafts-panasonic-wave200-2026-07-29.json`
- SHA-256: `b85c3f0bc8e89f74df35270c1e16f1be1e2e7d2e6c7250735fab1b379c3a0861`

Laravel:

- staging refresh: run 919/920, публикаций нет;
- dry-run применения: `Validated 125`, ошибок нет;
- применение: `Applied 125`, ошибок нет.

## Контроль до/после

Снимки:

- до: `docs/audits/generated/rb-panasonic-wave200-preapply-snapshot.json`  
  SHA-256: `97189e5eb3379cbb7bde60c9347a3a8aa5b414e05eebfe25eb6cded56d8b5a88`
- после: `docs/audits/generated/rb-panasonic-wave200-postapply-snapshot.json`  
  SHA-256: `3fc64eef733860111ad62d9d89b5fc020d853718cfc0f97f77eaa369ea74f3d8`

`scripts/verify-rb-panasonic-wave200-application.py` подтвердил:

- 125/125 описаний обновлены;
- 125/125 пустых manufacturers заполнены значением Panasonic;
- коммерческих изменений: 0;
- SEO-изменений: 0;
- ошибок соответствия официальным атрибутам: 0.

Поскольку поля `mpn`, `sku` и `name` не изменились ни у одной карточки, волна не могла создать новые дубли идентификаторов.

## Регрессия

- Panasonic Python suite: **13 passed**.
- Manufacturer-primary Laravel suite: **20 tests, 52 assertions passed**.
- Runtime verifier: **125/125**, price evidence **0**, errors **0**.
- `php artisan seo:audit microchips-by --json`: **passed**, 16 858 URL, 92 redirect, 0 блокеров.
- SSR smoke:
  - `/catalog/primary-cells/legacy-bitrix-765` — 200, Panasonic, noindex;
  - `/catalog/primary-cells/legacy-bitrix-766` — 200, Panasonic, noindex;
  - `/catalog/primary-cells/legacy-bitrix-775` — 200, Panasonic, noindex.

## Граница готовности

Эта волна повышает полноту карточек, но сама по себе не переводит проект через следующий общий порог +10%: карточки остаются безопасным preview до подтверждения изображений и коммерческих фактов. Общая подтверждённая готовность проекта остаётся **60%**.
