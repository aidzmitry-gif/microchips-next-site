# Текущий статус реализации

Дата фиксации: 2026-07-14.

## Доставлено и проверено

- Laravel 13.19, Filament 5.6, Horizon 5.47, Next.js 16.2, React 19 и PostgreSQL/Redis Docker-контур зафиксированы lockfile-ами и versioned image tags.
- Реализованы `SiteResolver`, shared `products` и site-scoped каталог/страницы/SEO/URL/301/контакты/интеграции.
- Реализованы API contract, SSR-витрина, self-canonical, sitemap, robots и защищённый endpoint revalidation.
- Реализованы Filament-ресурсы для профилей сайтов и общего каталога, staging CSV 1С, очередь Bitrix24 и 4 API-теста.
- Добавлен контролируемый путь импорта: валидация staging-данных → проверка дубликатов → ручное подтверждение → черновая site-scoped публикация с audit trail.
- Добавлены SEO release-аудит, единый quality gate и GitHub Actions workflow; они ловят cross-country canonical, разорванный `hreflang`, проблемные 301 и неиндексируемые URL в sitemap.
- Добавлен детерминированный реестр legacy URL: 22 796 sitemap URL и 5 471 старое redirect-правило классифицируются без переноса старых target URL в новую карту 301.
- Добавлены read-only public SEO snapshot и migration regression gate. Они подтверждают priority URL-паттерны на старом сайте и блокируют цепочки 301, homepage fallback, cross-country URL/canonical и `remove` с HTTP 200.
- Добавлены standalone HTML-визуальное ТЗ первой RB B2B-категории, статический SEO/lead gate и SSR/API-контракт переноса. Условия их использования и публикации определяет [политика допуска к публикации](standards/launch-policy.md).
- Добавлен read-only B2B-срез резервной копии: 2 856 parent-кандидатов, из которых 1 569 входят в первый ИБП/резервный review-фокус с учётом всех section memberships. Guard обнаружил 12 активных SKU-offer записей в infoblock 28/67 и блокирует новый экспорт до reconciliation; отсутствие article/SKU/MPN у parent-строк не объявляется доказательством отсутствия идентичности во всём источнике.

Проверки инженерного цикла: единый quality gate пройден локально и в GitHub Actions на `main` — PHP lint, Laravel Pint, PHPUnit (18 тестов/89 assertions), Next.js production build и `docker compose config`. В частности, remote CI подтвердил тесты staging/review/publish для каталога. Локальный `seo:audit microchips-by --json` пройден: 1 индексируемый URL в sitemap, 0 блокирующих ошибок. Docker Desktop на рабочей машине не запущен, поэтому compose-build и PostgreSQL/Horizon integration-test ещё не подтверждены.

## Честный прогресс

| Часть | Вес | Подтверждённая готовность | Вклад |
| --- | ---: | ---: | ---: |
| 1. Multi-site foundation | 12% | 65% — функциональный каркас и tests/CI подтверждены; реальные staging/production ещё нет | 7,8% |
| 2. Source audit и SEO registry | 13% | 90% — есть повторяемый registry, regression tests/CI и live priority crawl; нет preview/staging для воспроизводимой cutover-проверки | 11,7% |
| 3. Shared catalog и import core | 15% | 65% — подтверждены безопасный review/publish workflow и tests/CI; реальная 1С-выгрузка и воспроизводимый deploy ещё не подтверждены | 9,75% |
| 4. Regional SEO/GEO | 10% | 90% — подтверждены release gate, sitemap-аудит и tests/CI; production crawl и локальный коммерческий контент не подтверждены | 9,0% |
| 5. Беларусь | 15% | 0% | 0% |
| 6. Россия | 15% | 0% | 0% |
| 7. Узбекистан | 12% | 0% | 0% |
| 8. Сайт 4 и operating standard | 8% | 0% | 0% |
| **Итого** | **100%** |  | **38,25%** |

Формула: `Σ(вес части × verified readiness) / 100`. Частичный код не засчитывается как SEO-готовность: до заполнения всех критериев страны её готовность всегда `0%`.

## Следующий объективный гейт — Gate 0

Нужна выгрузка 1С или прайс поставщика минимум для **50 товаров утверждённого
RB-фокуса**. Для каждой позиции требуется источник, стабильный supplier/1C ID,
SKU/MPN (если применим), название, категория и явное решение по дублю или
пропуску. До её получения текущие кандидаты остаются `needs_review`; это не
влияет на зафиксированные **38,25%** готовности.

Gate 0 разрешает только проверку малого staging-среза. Условия Gate 0 и все
последующие блокеры публикации/запуска страны определены в
[политике допуска к публикации](standards/launch-policy.md).
