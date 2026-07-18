# Текущий статус реализации

Дата фиксации: 2026-07-14. Обновлено: 2026-07-18 (конвертер staging CSV + E2E-тест, лист «Цены и наличие», аудит конвейера — проценты без изменений, см. ниже).

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
- Добавлен конвертер `scripts/build-rb-staging-csv.ps1` (манифест → staging CSV для `catalog:stage-1c`): `external_id` берётся строго из `supplier_or_1c_id`, `sku`/`mpn` — только из подтверждённых колонок манифеста, кандидаты (`brand_candidate`, `mpn_candidate_from_name`) в `sku`/`mpn` не попадают ни при одном ветвлении. Добавлен E2E-тест `backend/tests/Feature/RbStagingConverterPipelineTest.php` (2 теста) на реальном байт-в-байт фикстурном выводе конвертера (`tests/Fixtures/rb-staging-1c.golden.csv`): проверяет отсутствие UTF-8 BOM, корректный quoted-заголовок `external_id`, приёмку `catalog:stage-1c` и то, что «отравленный» кандидат-сентинел не просачивается в staging. Прогнан локально зелёным (php с включёнными `pdo_sqlite`/`mbstring`): весь бэкенд-набор — 20 тестов/104 assertions, из них новый файл — 2 теста/15 assertions.
- Добавлен лист «Цены и наличие» в `scripts/build-nomenclature-xlsx.py` (join с `docs/audits/generated/rb-import-manifest-draft.csv` по `legacy_element_id`): заголовок листа явно предупреждает «не живые данные, по состоянию на дату бэкапа Bitrix», пустые ячейки остаются пустыми (не подставляются). Открыт и проверен в этой сессии через `openpyxl.load_workbook`: лист присутствует, 91 строка (заголовки + 88 товаров), структура и предупреждение подтверждены.

Проверки инженерного цикла: единый quality gate пройден локально и в GitHub Actions на `main` — PHP lint, Laravel Pint, PHPUnit (CI: 18 тестов/89 assertions; локально после +2 тестов конвертера — 20 тестов/104 assertions зелёные, CI-прогон для этой ветки ещё не запускался), Next.js production build и `docker compose config`. В частности, remote CI подтвердил тесты staging/review/publish для каталога. Локальный `seo:audit microchips-by --json` пройден: 1 индексируемый URL в sitemap, 0 блокирующих ошибок. Docker Desktop на рабочей машине в этой сессии запущен и отвечает: `docker compose config` прошёл валидацию, `docker compose build` стартовал без ошибок (пул базовых образов, первые build-стадии), но прогон был прерван по таймауту до завершения — полный build и PostgreSQL/Horizon integration-test (`docker compose up` + health checks) по-прежнему НЕ подтверждены.

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

## Находки аудита конвейера (2026-07-18) — исправлены

Read-only аудит конвейера manifest → staging CSV → backend нашёл два дефекта; оба закрыты в этой сессии:

- **CONFIRMED (утечка бренда) — исправлено.** Флаг `-IncludeBrandCandidate` мог писать неподтверждённый `brand_candidate` в `manufacturer` → `Product.manufacturer` без пометки «кандидат», делая эвристику неотличимой от подтверждённого производителя (запрещённый правилом честности сценарий). Флаг удалён целиком: `manufacturer` теперь всегда пуст (подтверждённого источника бренда в манифесте нет). Self-test проверяет инвариант «manufacturer всегда пуст» на всех выходных строках.
- **PLAUSIBLE (кодировка) — исправлено.** `Import-Csv` манифеста получил явный `-Encoding UTF8` (как в родственном `scripts/build-legacy-url-decision-registry.ps1`) — снижает риск молчаливой порчи кириллицы при ре-сейве манифеста из Excel. Проверено, что реальный BOM-драфт по-прежнему читается корректно.

## Следующий объективный гейт — Gate 0

Нужна выгрузка 1С или прайс поставщика минимум для **50 товаров утверждённого
RB-фокуса**. Для каждой позиции требуется источник, стабильный supplier/1C ID,
SKU/MPN (если применим), название, категория и явное решение по дублю или
пропуску. До её получения текущие кандидаты остаются `needs_review`; это не
влияет на зафиксированные **38,25%** готовности.

Gate 0 разрешает только проверку малого staging-среза. Условия Gate 0 и все
последующие блокеры публикации/запуска страны определены в
[политике допуска к публикации](standards/launch-policy.md).
