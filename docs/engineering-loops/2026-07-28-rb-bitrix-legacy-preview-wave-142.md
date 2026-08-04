# RB Bitrix legacy preview — wave 142

Дата: 2026-07-28  
Рынок: Беларусь (`microchips-by`)  
Назначение: визуально проверить полный перенос старого каталога до очистки и канонической публикации.

## Результат цикла

- Создан отдельный read-only API старого снимка Bitrix run `742`.
- Созданы локальные страницы:
  - `/legacy-preview/catalog` — дерево, поиск, статусы, сортировка, пагинация;
  - `/legacy-preview/catalog/{category}` — просмотр раздела и потомков;
  - `/legacy-preview/product/{legacyId}` — исходная карточка и связи с 1С;
  - `/api/legacy-preview/media/{legacyId}` — закрытый frontend-proxy архивного изображения.
- В интерфейсе доступны `1 562` активные профильные позиции из снимка `1 569`:
  - `6` неактивных legacy-позиций исключены;
  - `1` электронная позиция исключена по текущему решению о границах каталога.
- Подключено исходное дерево `220` Bitrix-разделов и `1 568` проверенных файлов архивных изображений.
- Старый HTML не возвращается: API удаляет `script/style`, теги, управляющие символы и отдаёт только нормализованный plain text.

## Fail-closed границы

- API работает только для активного профиля с доменом `.test`.
- Frontend открывает preview только с `localhost`, `127.0.0.1`, `::1` или `.test`.
- Все ответы имеют `Cache-Control: private, no-store` и `X-Robots-Tag: noindex, nofollow, noarchive`.
- Страницы имеют meta robots `noindex,nofollow,nocache` и запрещены в `robots.txt`.
- Preview не использует публичные `SiteUrl`, `SiteSeo`, `ProductMedia`, `CatalogView` или `ProductView`.
- Не показываются цена, наличие, форма заказа, коммерческие условия, Product/Offer schema.
- Ни один preview-запрос не изменяет `SiteProduct`, публикацию, sitemap или staging-записи.

## Подтверждённые счётчики

| Проверка | Результат |
|---|---:|
| Снимок Bitrix | 1 569 |
| Доступно в профильном preview | 1 562 |
| Исключено из preview | 7 |
| Bitrix-разделы в staging | 220 |
| Опубликованные Bitrix-разделы | 0 |
| Staged rows с `published_at` | 0 |
| Staged rows с `published_product_id` | 0 |
| Публичные RB site-products до/после | 233 / 233 |
| SEO blockers | 0 |

## Верификация

- Laravel isolated SQLite test: `2` tests, `37` assertions — PASS.
- Frontend Vitest: `2` files, `9` tests — PASS.
- TypeScript `tsc --noEmit` — PASS.
- ESLint — `0` errors; остались `3` ранее существовавших warning вне preview.
- Next.js 16.2.10 production Docker build — PASS; оба новых маршрута вошли в route manifest.
- Playwright mock contour:
  - desktop/mobile: `3` PASS, `1` ожидаемо skipped;
  - horizontal overflow отсутствует;
  - noindex подтверждён;
  - коммерческие утверждения и Offer отсутствуют.
- Реальный Docker smoke:
  - categories API: HTTP 200, `0.406 s`;
  - frontend preview: HTTP 200, `0.660 s`;
  - media proxy: HTTP 200 JPEG, `0.111 s`;
  - sitemap до/после байт-в-байт совпадает и не содержит `legacy-preview`;
  - public catalog API до/после совпадает.
- `php artisan seo:audit microchips-by --json`: `261` URL, `0` blockers, PASS.

## Готовность

- Безопасный первичный перенос старого каталога: **90%**. Остались документы/некаталожные страницы и итоговый регрессионный пакет миграции URL.
- Готовность канонического очищенного каталога не увеличивается только за счёт preview: строгий показатель остаётся `77 / 7 286 = 1,06%` полностью подтверждённых карточек.
- Следующий цикл: использовать этот preview как baseline для пакетного дедупа и новой SEO-таксономии; старое дерево и тексты не переносить в публичный слой автоматически.
