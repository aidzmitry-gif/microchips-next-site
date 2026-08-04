# Текущий статус реализации

Дата фиксации: 2026-07-14. Обновлено: 2026-07-26 (полная выгрузка 1С 9 209 строк, очередь 109 связей Bitrix ↔ 1С, Filament-проверка и защита от перекрёстных дублей; затем владелец подтвердил локальный коммерческий профиль РБ, закрыты automated regression, evidence-backed catalog/local-inbox validation, локальный SEO/GEO-package и изолированная backup/restore-проверка → готовность 40,05% → 45,0% → 48,75% → 51,0% → 54,0% → 60,0%).

## Контрольный срез локального контура — 2026-07-26

- Локальный Docker-контур после полного пересоздания сервисов healthy; backend
  подтвердил доступ к PostgreSQL прикладным запросом.
- В shared-каталоге **50** проверенных позиций и **50** site-scoped черновиков
  для Беларуси. Все они намеренно `is_published=false`: витрина не должна
  открываться до заполнения и проверки местных коммерческих фактов.
- В staging **50** записей со статусом `published` в смысле «безопасно созданы
  в черновом каталоге», а не «видимы покупателю»; `publication_snapshot`
  фиксирует `publicly_visible=false`. Открытых `duplicate_conflicts` — **0**.
- Импортированы 4 категории и 0 из них опубликованы. Все 50 черновиков имеют
  ровно одну привязку к дереву (`50/50`, dry-run assignment CSV: 0 ошибок),
  но публичные URL не объявляются готовыми до странового SEO release-аудита.
- Проверка текущей рабочей копии: PHP syntax + Pint прошли; PHPUnit — **293
  тестов / 1 169 assertions**; Vitest — **75 тестов**; Next.js production build
  прошёл. `docker compose config --quiet`, self-test публичного release-checker
  и локальный `seo:audit microchips-by --json` также зелёные. На Windows Vite
  требует запуск вне sandbox (внутри него `spawn EPERM` до выполнения тестов);
  вне sandbox тесты и build прошли.
- Закрыты runtime-инварианты до включения индексации: внешний или ненормальный
  redirect-target не выходит из API/resolver; карточки и дерево каталога
  запрашивают URL выбранной enabled locale; `hreflang` отбрасывает alternate,
  который не может разрешиться из-за несовпадения locale URL и страницы.
  Регрессия подтверждена backend **272/272** (1 077 assertions), frontend
  **74/74** и production build.
- Шапка получает locale-scoped map опубликованных страниц и строит ссылку по
  логическому slug страницы, а не по жёстко заданному RU-пути. Это исключает
  переход с `uz-UZ` на другой язык при отличающихся URL.
- Docker smoke в CI переведён с base Compose на production deployment graph:
  проверяются `migrate` dependency и bindings только `127.0.0.1`. Локальная
  production Compose-конфигурация валидна с CI-параметрами. Изолированный
  local production smoke выполнил полный graph: `migrate` завершился до
  backend, `/admin/login` и `robots.txt` ответили `200`, порты были
  `127.0.0.1:18080/13000`, после проверки временные containers и volumes
  удалены. Remote GitHub Actions ещё нужен как независимое подтверждение
  обновлённого workflow.
- Полный read-only Bitrix цикл `extract → manifest → nomenclature audit`
  воспроизведён из локального snapshot: focus **1 569** (`1 445` primary,
  `81 + 43` additional), 12 активных offer-элементов признаны reviewed
  out-of-scope, `CML2_LINK` к parent-каталогу не найдено. В source остаются
  93 findings для исправления (23 high, 69 medium, 1 low); это evidence для
  миграции, а не разрешение публиковать товары.
- В staging исключены скрытые cross-field дубли: `SKU=X` и `MPN=X` теперь
  считаются одной identity namespace как для новой CSV-строки, так и для уже
  существующего shared product. CSV с повторяющимися нормализованными
  заголовками (например, `sku` и `SKU`) fail-closed до записи строк.
- Чистый production-контур теперь имеет отдельную fail-closed команду
  `admin:bootstrap`: она создаёт только первого администратора, не использует
  demo seed и отказывается работать после появления администратора. CI явно
  проверяет, что неинициализированный домен отвечает `robots` с `Disallow: /`,
  а не выдаёт пустой контур за готовую витрину.

- Владелец 2026-07-26 подтвердил профиль РБ: ООО «Аккумуляторные решения»,
  УНП 192766048; юридический адрес — пом. 407, самовывоз — офис 408,
  пн–пт 9:00–17:00; два телефона, `order@microchips.by`, BYN, безналичная
  оплата по счёту, самовывоз по подтверждению менеджера, доставка
  «Автолайтэкспресс» и условия гарантии/возврата. В локальном site profile
  опубликованы как **verified** 7 contact и 5 commercial fact с audit note;
  ни витрина, ни товарные URL от этого не опубликованы. Новый release-аудит
  блокирует индексируемую `/warranty` без verified `warranty_terms`.
- Профиль РБ воспроизводим через
  `docs/imports/rb-commercial-profile-drafts.json` и fail-closed команду
  `site:import-commercial-profile-drafts`: она создаёт только черновики,
  не меняет verification у совпадающей записи и отказывается заменить
  verified-значение другим текстом. Локальный dry-run/apply подтвердил
  `7 contacts unchanged` и `5 facts unchanged`.
- Лиды доступны оператору в отдельном Filament-разделе: выводятся сайт,
  локаль, контакт, UTM, корзина и локальный lifecycle. Для первого этапа
  local inbox — рабочий канал; Bitrix24 остаётся необязательной интеграцией.
- Витрина получила SSR-блок локальных реквизитов, оплаты, доставки и
  гарантии, но исключительно из полного набора verified site-scoped данных
  нужной locale. В `not_found`/redirect API-ответах этот блок отсутствует:
  подтверждённые сведения не раскрываются до опубликованного контента.
- Добавлена `site:launch-preflight`: read-only сводка configured launch
  blockers поверх SEO-audit. Текущий RB-профиль честно блокируется по
  `INDEXABLE_URL_MISSING`; внешний DNS/TLS, реальный обработанный local-inbox
  lead и кабинеты вебмастеров команда не имитирует.
- Для первого этапа без Bitrix24 реализован local-inbox: заявка получает
  lifecycle `new → in_progress → closed`, ответственного, дату и обязательную
  итоговую заметку. В Filament доступны только эти auditable действия; данные
  клиента не редактируются. Миграция применена к локальному Docker, маршрут
  `/admin/leads` защищён стандартной авторизацией.

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

Проверки инженерного цикла: единый quality gate пройден локально и в GitHub Actions — PHP lint, Laravel Pint, PHPUnit, frontend vitest, Next.js production build и `docker compose config`. Покрытие тестами резко поднято (2026-07-19): backend **143 теста / 492 assertions**, frontend **36 тестов** (vitest-инфраструктура добавлена с нуля), измеренный в CI **line-coverage 98.30%** (1390/1414, через pcov). Остаток непокрыт сознательно (недостижимые defensive-ветки под FK/контрактами + relation-boilerplate моделей). По пути найдено и починено 2 реальных бага: `StageOneCCatalog` ragged-row (array_combine ValueError на PHP 8 валил весь импорт) и `DuplicateConflictResource` (краш Filament-списка конфликтов). В частности, remote CI подтвердил тесты staging/review/publish для каталога. Локальный `seo:audit microchips-by --json` пройден: 1 индексируемый URL в sitemap, 0 блокирующих ошибок. Docker-контур подтверждён на рабочей машине (2026-07-18): `docker compose build` собирает все 6 образов, `docker compose up -d` поднимает стек (backend, worker, nginx, frontend + postgres/redis healthy), `php artisan migrate --force` создал 26 таблиц в PostgreSQL, Horizon-worker стабильно `running` (RestartCount=0, «Horizon is running»), backend роутит на Filament `/admin/login`. Для этого пришлось починить 5 реальных багов `backend/Dockerfile` (образ backend раньше не собирался вообще): `--ignore-platform-req` intl/pcntl для `composer install`; `--no-scripts` в `dump-autoload`; `libpq-dev`+`icu-dev` для `pdo_pgsql`/`intl`; убран `opcache` из ext-install (уже built-in); добавлен `phpredis` (нужен Horizon). Плюс `backend/.dockerignore` (не тащить stale `bootstrap/cache` с dev-пакетами) и `frontend/Dockerfile` (пути standalone в pnpm-монорепо). Остаётся неподтверждённым только развёрнутый staging/production (домен + внешняя доступность) и наполнение `sites`/каталога реальными данными.

## Честный прогресс

| Часть | Вес | Подтверждённая готовность | Вклад |
| --- | ---: | ---: | ---: |
| 1. Multi-site foundation | 12% | 90% — каркас, tests/CI и production Docker-контур (build + migrate dependency + HTTP + loopback ports) подтверждены локально; остаётся внешний staging/production и remote CI для обновлённого workflow | 10,8% |
| 2. Source audit и SEO registry | 13% | 90% — есть повторяемый registry, regression tests/CI и live priority crawl; нет preview/staging для воспроизводимой cutover-проверки | 11,7% |
| 3. Shared catalog и import core | 15% | 90% — подтверждены безопасный review/publish workflow, tests/CI, полная реальная выгрузка 1С (9 209 строк) и идемпотентная очередь 109 связей Bitrix ↔ 1С; воспроизводимый production-deploy и регламентный ночной обмен ещё не подтверждены | 13,5% |
| 4. Regional SEO/GEO | 10% | 90% — подтверждены release gate, sitemap-аудит и tests/CI; production crawl и локальный коммерческий контент не подтверждены | 9,0% |
| 5. Беларусь | 15% | 100% implementation readiness — «локальные коммерческие и юридические данные»: 7 verified contacts и 5 verified commercial facts; «SEO/GEO и локализованный контент»: 4 RB commercial pages разрешаются только с noindex, canonical/SEO audit без blockers; «каталог и обработка заявки»: 50 evidence-backed non-public drafts, 50/50 category links, local inbox lifecycle; «автоматическая регрессия»: backend fixture-gate, Next.js SSR E2E и mobile E2E; «monitoring, backup и launch checklist»: Filament-widget, preflight и фактическое изолированное PostgreSQL restore. Это не означает разрешение внешнего launch. | 15,0% |
| 6. Россия | 15% | 0% | 0% |
| 7. Узбекистан | 12% | 0% | 0% |
| 8. Сайт 4 и operating standard | 8% | 0% | 0% |
| **Итого** | **100%** |  | **60,0%** |

Формула: `Σ(вес части × verified readiness) / 100`. Для страны засчитывается
только полностью завершённый взвешенный критерий; частично выполненный
критерий даёт `0%`. РБ implementation-ready, но не launch-ready: перед
внешней публикацией обязательны staging DNS/TLS, отдельные Analytics + Search
Console/Yandex Webmaster, внешний crawl, утверждённая redirect cutover-карта
и устранение 93 находок исходного номенклатурного аудита. Товарные URL и
indexability намеренно остаются выключенными.

## Находки аудита конвейера (2026-07-18) — исправлены

Read-only аудит конвейера manifest → staging CSV → backend нашёл два дефекта; оба закрыты в этой сессии:

- **CONFIRMED (утечка бренда) — исправлено.** Флаг `-IncludeBrandCandidate` мог писать неподтверждённый `brand_candidate` в `manufacturer` → `Product.manufacturer` без пометки «кандидат», делая эвристику неотличимой от подтверждённого производителя (запрещённый правилом честности сценарий). Флаг удалён целиком: `manufacturer` теперь всегда пуст (подтверждённого источника бренда в манифесте нет). Self-test проверяет инвариант «manufacturer всегда пуст» на всех выходных строках.
- **PLAUSIBLE (кодировка) — исправлено.** `Import-Csv` манифеста получил явный `-Encoding UTF8` (как в родственном `scripts/build-legacy-url-decision-registry.ps1`) — снижает риск молчаливой порчи кириллицы при ре-сейве манифеста из Excel. Проверено, что реальный BOM-драфт по-прежнему читается корректно.

## Следующий объективный гейт — запуск страны

Полная выгрузка 1С уже инвентаризирована, а проверенный малый срез загружен
только как черновик. Локальные реквизиты/контакты и коммерческие правила РБ
уже подтверждены, но это не заменяет country launch evidence. Для Беларуси,
а затем для каждой следующей страны, нужны: реальный обработанный local-inbox lead,
отдельные Analytics + Search Console/Yandex Webmaster, staging с DNS/TLS,
локализованный SEO/GEO-контент и внешний SEO-crawl. До этого `is_published`
у товарных URL и indexability не включаются.

Условия каждого launch gate определены в
[политике допуска к публикации](standards/launch-policy.md).
