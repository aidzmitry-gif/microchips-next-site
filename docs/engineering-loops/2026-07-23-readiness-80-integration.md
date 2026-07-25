# Интеграционный цикл готовности: 2026-07-23

## Цель и принцип

Цель цикла — убрать автономные технические разрывы, не подменяя внешние
подтверждения (1С-идентичность, юридические данные, DNS, production crawl)
предположениями. Поэтому «80% готовности» не является результатом этого
цикла: используется утвержденная формула из `docs/implementation-status.md`.

Стартовая подтвержденная готовность: **43,8%**. После этого цикла она
сохраняется **43,8%**, пока не закрыты условия запуска стран и production
гейты. Улучшены инженерные доказательства и устранены риски дрейфа.

## Реализовано

1. **Дерево и фильтрация каталога**
   - Добавлены site-scoped `source`/`external_id` для категорий и pivot
     `site_category_product` с запретом перекрестной привязки сайтов.
   - API выдаёт опубликованное дерево и фильтрует товары по категории вместе
     с опубликованными потомками. SSR-страница передаёт выбранную категорию в
     API, поэтому URL категории не показывает весь каталог.
   - Добавлен dry-run импортатор дерева. По умолчанию он делает rollback и
     создаёт `ImportRun`; `--apply` нужен явно. Неизвестный родитель блокирует
     весь импорт.

2. **Витрина и заявки**
   - Добавлены SSR-вью карточки товара, состояния loading/error/not-found и
     безопасная вставка schema из API.
   - Форма КП повторяет контракт Laravel: `company`, `contact_name`, отдельные
     `email`/`phone`, абсолютный `page_url`, locale, UTM и корзина. Proxy не
     пересылает контролируемый браузером `X-Forwarded-For` в rate limit API.
   - `robots.txt` запрещает обход сайта, пока текущий hostname нельзя
     разрешить в индексируемый профиль.

3. **Инвалидация и эксплуатация**
   - Изменения категории и её состава отправляют revalidate только для URL
     затронутой категории; это закрывает stale-страницу списка после смены
     состава каталога.
   - Добавлены healthchecks и зависимости сервисов Docker, CI smoke-job
     (build, запуск, миграция, HTTP, backup/isolated restore), а также скрипт
     проверки backup/restore PostgreSQL в отдельную временную БД.

4. **Адверсариальная интеграционная проверка**
   - Устранён разрыв «API-дерево есть, но интерфейс показывает RB-статический
     список»: header и каталог получают site-scoped дерево и только URL,
     опубликованные для текущего locale.
   - API карточек возвращает site-scoped URL товара. Если URL не опубликован,
     интерфейс не создаёт ложную ссылку на карточку.
   - Заявка сверяет hostname `page_url` с выбранным `site_key`, принимает UTM
     и cart; недостоверная межстрановая атрибуция отклоняется. Лимит заявок
     использует серверный HttpOnly rate key, а не общий IP контейнера.
   - `Offer` JSON-LD удаляется на сервере, пока у опубликованного товара нет
     подтверждённой локальной цены и `in_stock` availability.
   - Importer блокирует shared canonical category вместо опасного неидемпотентного
     клонирования; пути категорий нормализуются по регистру. Изменение товара
     или дочерней категории инвалидирует также страницы опубликованных предков.

## Доказательства этого запуска

| Проверка | Результат |
| --- | --- |
| Laravel PHPUnit | 176 тестов, 664 assertion — passed |
| Laravel Pint | passed |
| Vitest | 60 тестов — passed |
| Next.js production build | passed (Next 16.2.10) |
| Проверка HTML-визуальных ТЗ | 4 из 4 prototype — passed |
| Docker Compose config | passed |
| Dry-run фактического CSV дерева | 219 категорий валидны при 4 явно объявленных внешних родителях |

## Найденная граница данных

Первый dry-run `docs/imports/site-catalog-full-categories.csv` был корректно
заблокирован: в CSV шесть ссылок на отсутствующих родителей, с external ID
`372`, `489`, `1090`, `1091`. После явного объявления этой границы через
`--allow-missing-parent` CSV валиден: **219** категорий, **219** потенциальных
созданий, без записи в БД. Применение запрещено до решения, являются ли эти
четыре родителя внешней границей или недостающими строками источника.

Повторный read-only проход по локальной копии Bitrix подтвердил актуальные
счётчики фокуса: **1 569** кандидатов по любому section membership, из них
**1 445** primary, **81** — дополнительная привязка к целевому разделу и
**43** — дополнительная привязка извне среза. Гейт намеренно остановил вывод:
в offer-инфоблоках 28/67 найдены **12 активных элементов**, две `CML2_LINK`
свойства и ноль ссылок на catalog parents. До reconciliation офферы не могут
считаться пустыми, а новые generated evidence не записываются.

## Непройденные внешние гейты

- Подтверждённая identity для хотя бы 50 товаров фокуса: SKU/MPN или иной
  стабильный 1С/поставщицкий идентификатор и решение по дублям.
- Решение для 12 SKU-offer из Bitrix и публикация только после review.
- Настоящие юридические, коммерческие, контактные и доставочные данные для BY,
  затем RU/UZ/четвёртого рынка.
- Staging/production: DNS/TLS, внешняя доступность, реальный Bitrix24 lead,
  Search Console/Yandex Webmaster/analytics, финальная 301-карта и crawl.
- Локальный runtime Docker smoke не выполнен в этом запуске: Docker Desktop
  был выключен. CI-job добавлен, но его remote запуск ещё не подтверждён.

## Следующее безопасное действие

Получить решение по четырём parent ID и выгрузку идентичности из 1С/прайса.
После этого: повторить dry-run без исключений либо с документированной
границей, применить только draft-категории в staging и проверить первый
review-batch без публикации.
## Final verification update (2026-07-23)

- The real read-only Bitrix pipeline completed: extract, manifest and
  nomenclature audit. It retained all **1,569** focus candidates (1,445
  primary and 124 additional memberships). The audit produced 93 findings for
  88 products; all remain `needs_review`.
- The 12 active offer rows are exact reviewed, unlinked footwear orphans in
  iblock 67. They remain non-migratable migration debt. The narrow extractor
  exception applies only to their fixed IDs without a `CML2_LINK` value; any
  new, changed or linked offer re-enables the hard stop.
- SEO release safety now excludes noindex/non-canonical/unpublished hreflang
  alternates, returns `noindex,follow` for query variants, and preserves exact
  redirect statuses in the hostname-aware Next proxy.

| Check | Verified result |
| --- | --- |
| Laravel PHPUnit | 180 tests, 675 assertions — passed |
| Laravel Pint | passed |
| Vitest | 63 tests — passed |
| Next.js production build | passed (Next 16.2.10) |
| RB HTML visual prototype check | 4 of 4 — passed |
| Docker Compose configuration | passed (runtime smoke still requires Docker Desktop) |
| Git diff whitespace check | passed |

The verified readiness remains **43.8%** under the agreed weighted formula.
This engineering loop removed autonomous implementation risk but cannot count
unverified identity, regional legal/commercial data, staging/production, or
the post-launch observation period as completed work.
## P1 hardening update (2026-07-23)

The second autonomous loop closed verified content-change and deployment risks:

- Resolver indexability is now the conjunction of `site_urls.is_indexable` and
  resource SEO settings. A URL marked noindex cannot become indexable merely
  because it has no `site_seos` row.
- A disabled non-default locale is rejected before a lead is persisted or sent
  to CRM. The hreflang audit now applies the site's default locale when a URL
  stores `locale = NULL`.
- URL rename/delete, SEO, redirects and hreflang changes dispatch selective
  Next revalidation for affected paths and the sitemap. This removes the
  previous five-minute stale-cache window after an admin change.
- Redirect lookup in the Next proxy has a 1.5-second upper bound and fails
  open to normal SSR on upstream failure. Baseline browser security headers
  are emitted by the storefront.
- `docker-compose.production.yml` keeps application ports on localhost,
  applies restart policies, and makes migrations a prerequisite for backend
  and Horizon. `scripts/release-preflight.sh` and CI validate the required
  HTTPS URL and non-placeholder secrets without storing them in git.

Verification after this update: Laravel PHPUnit **185 tests / 687
assertions**, Pint, Vitest **65 tests**, Next production build, prototype
verification and both base/production Compose configurations passed.

Verified readiness remains **43.8%**. Deployment code is evidence for the
foundation, but a real staging/production deployment, host-based crawl and
post-launch observation remain external gates and cannot be counted early.
### Availability semantics addendum

The sitemap route now propagates an upstream API failure instead of returning
an empty successful sitemap. The dynamic page route throws its server error
when the resolver is unavailable rather than rendering an indexable-looking
200 fallback. Healthy empty catalogues and healthy empty sitemaps still work
normally. Frontend verification after this change: **66 tests** and a passing
Next.js production build.
### Locale switcher addendum

Resolver SEO payloads now include their effective locale. The storefront uses
that value plus only verified HTTPS hreflang URLs to render a visible
country/language selector for the current page. It deliberately omits any
locale without a safe, reciprocal URL rather than guessing a localized route.
Verification: frontend **67 tests** and production build passed; the related
backend API test and Pint passed.
### Document language addendum

The hostname/path redirect lookup now returns the effective locale of the
matched URL (or the site default). The Next proxy forwards only its validated
language subtag to the root server layout, so the rendered document has
`lang="ru"` or `lang="uz"` without IP geo-detection. Frontend verification:
**70 tests** and production build passed; the backend redirect contract test
passed.
### Database boundary addendum

`site_category_product` now has composite foreign keys against
`(site_id, id)` for both site categories and site products. This enforces the
same-market boundary for direct query-builder or raw SQL writes, not only for
the Eloquent pivot model. The migration is covered by a test that attempts the
previous cross-site raw insert and expects the database to reject it.
