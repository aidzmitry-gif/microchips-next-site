# Wave242E — дата наблюдения цены в публичном UI

Дата: 2026-07-29  
Контур: Беларусь (`microchips.by`)

## Что изменено

- Catalogue API и product resolve API отдают `price_observed_at` только из текущего price evidence, если его `calculated_price` и `currency` совпадают с опубликованными ценой и валютой.
- Связь с текущим evidence загружается заранее для карточек каталога, основного товара и вариантов, поэтому поле не создаёт N+1-запросов.
- Рядом с числовой ценой показана подпись `Цена по данным на ДД.ММ.ГГГГ · уточняйте`; `availability` остаётся отдельным статусом.
- При `price=null`, отсутствующем, несовпадающем или некорректном evidence подпись не показывается.

## Инварианты

Не изменялись числовые цены, флаги `is_current`, availability, публикация, Offer schema, URL и схема базы данных. Миграции не применялись.

## Проверка

- PHP syntax: `SiteProduct.php`, `CatalogController.php`, `SiteResolver.php` — без ошибок.
- Frontend targeted Vitest: 3 файла, 15 тестов — успешно.
- TypeScript: `npx tsc --noEmit` — успешно.
- Backend PHPUnit: 2 targeted tests / 23 assertions passed in PHP 8.5.8
  against an isolated migrated SQLite database. The first local attempt was
  correctly rejected because the host PHP lacked `mbstring`; the containerized
  run is the recorded verification result.
- Runtime API: a priced catalogue row and resolved product expose the pinned
  `2026-06-23` timestamp; the unpriced KM-300 P row exposes null; an
  `on_request` product emits no Offer schema.
- Production Next build and Docker rebuild passed; all six services are
  healthy. Mobile catalogue/tree and the evidence label were visually checked.
