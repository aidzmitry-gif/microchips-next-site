# Контракт переноса RB B2B HTML-прототипа

## Назначение и границы

`docs/prototypes/rb-b2b-catalog.html` — статический артефакт согласования
интерфейса для Беларуси. Он не является публичной страницей, не должен
индексироваться и не заменяет проверку в Laravel или Next.js. При переносе
каждая зона ниже получает данные только через site-scoped контракт: общий
товар не означает общие коммерческие условия.

## Карта зон прототипа

| Зона HTML | Next.js SSR | Laravel/API | Условие приёмки |
| --- | --- | --- | --- |
| Шапка, переключатель страны и языка | `frontend/src/app/[[...path]]/page.tsx` получает `site` на сервере и отображает домен, страну и включённые локали. Переключатель ведёт на уже разрешённый URL, без IP-редиректа. | `GET /api/v1/sites/{host}/resolve?path=`; `SiteResolver::resolve()` нормализует host и выбирает активный `Site`. | Страница на `microchips.by` не использует текст, контакты или валюту другого `site_id`; скрытый IP-switch запрещён. |
| Хлебные крошки, H1 и описание категории | SSR получает `category` и `seo` для текущего пути, а не собирает контент в браузере. | `SiteUrl` → `SiteCategory`, опубликованные записи только данного `site_id`. | Один видимый `h1`; локальный редактор утверждает текст до публикации. |
| Сетка товаров, спецификации и состояния «по запросу» | Компоненты используют `ProductPayload`; цена, валюта и доступность отображаются только из site-scoped данных. | `GET /api/v1/sites/{site}/catalog/products` и `SiteProduct::published()`; товар из `SiteProduct` связывается с общим `Product`. | Не показывать цену, склад, документ или сертификат без подтверждённых данных конкретного рынка. |
| Фильтр, сортировка и поиск | Состояние фильтра/поиска клиентское либо SSR с отдельным неиндексируемым URL. В indexable listing не подмешивать query-варианты. | Каталог допускает `q`, но публикация и видимость всегда ограничены `site_id`. | `/filter`, `/search`, `/sort`, query-комбинации, корзина и сравнение — `noindex,follow`, отсутствуют из sitemap и не становятся canonical indexable-страницы. |
| Карточка товара и SEO metadata | `generateMetadata()` в `frontend/src/app/[[...path]]/page.tsx` формирует title, description, robots, canonical и language alternates на сервере. | `SiteResolver::seoPayload()` возвращает `canonicalPath`, `isIndexable`, `hreflang`, `schema`. | Для indexable URL canonical равен его нормализованному пути на своём домене; hreflang reciprocal и только между реальными опубликованными локалями. |
| Заявка «Запросить КП» и мини-корзина | Форма содержит `company`, `contact_name`, раздельные `email`/`phone` и `message`. Клиентский mapper добавляет `site_key`, `locale`, абсолютный `page_url` и декодирует JSON `cart`/`utm`. Успех показывается только после `201`; повторная отправка блокируется на время запроса. | `POST /api/v1/leads/quote`; `LeadController` создаёт `Lead` с найденным `site_id`, locale, `page_url`, `cart`, `utm`, а потом ставит `SyncLeadToBitrix24` в очередь. | Локальная запись `Lead` — обязательна до фоновой CRM-синхронизации. Ошибка Bitrix24 не должна терять заявку или подменять её успешной отправкой. |
| Блок доверия, доставка, оплата, FAQ и контакты | SSR показывает только утверждённые RB-поля соответствующего site profile. | Данные хранятся per-site в `site_contacts`, `site_pages`, `site_seo` и интеграциях; общий каталог здесь не является источником. | До подтверждения юридического лица, адреса, оплаты и сервиса остаются явные placeholders и страница не получает коммерческую schema-разметку. |

## Неизменяемые правила SEO/GEO

1. В production `generateMetadata()` использует абсолютный self-canonical на
   `resolved.site.domain`; `canonicalPath` не содержит host, query или
   fragment. Это дополнительно блокируется `php artisan seo:audit {site}`.
2. `hreflang` выводится только для эквивалентных, действительно локализованных
   URL. Для Беларуси ожидается `ru-BY`; будущие `ru-RU`, `ru-UZ`, `uz-UZ`
   добавляются вместе с reciprocal URL, а не по умолчанию.
3. `robots.ts` и sitemap получают hostname на сервере через `getCurrentHost()`.
   Sitemap содержит только разрешённые indexable URLs конкретного домена.
4. JSON-LD `Product`/`Offer`, `LocalBusiness` и цены выводятся только после
   проверки местных коммерческих и юридических данных. Техническая часть
   `Product` допускается из общего каталога, но `Offer` без подтверждённой
   цены, валюты и доступности запрещён.
5. HTML-прототип обязан иметь `noindex, nofollow` и не задаёт fake canonical:
   его будущий canonical — свойство опубликованного SSR-route, а не файла ТЗ.

## Пакет данных для заявки

Перед `POST /api/v1/leads/quote` клиент собирает следующий объект. Названия
соответствуют текущей валидации `LeadController`.

```json
{
  "site_key": "microchips-by",
  "locale": "ru-BY",
  "company": "string",
  "contact_name": "string",
  "email": "name@example.by",
  "phone": "+375...",
  "message": "string",
  "page_url": "https://microchips.by/catalog/...",
  "cart": [{ "site_product_id": 0, "quantity": 1 }],
  "utm": { "utm_source": "...", "utm_medium": "...", "utm_campaign": "..." }
}
```

`site_key` — единственный client-facing selector; сервер сам находит активный
`Site`, записывает его внутренний `site_id`, а незаполненный locale заменяет
на `default_locale`. Нельзя принимать `site_id` из браузера. Поля `email` и
`phone` валидируются по правилу «хотя бы одно»; cart ограничен 100 позициями,
UTM — 30 полями. Состав корзины должен ссылаться на опубликованный
`SiteProduct` выбранного сайта до того, как интерфейс позволит отправить форму.

### Связь статического макета и API

`rb-b2b-catalog.html` показывает те же поля, что и `LeadController`, но имеет
`data-prototype-submission="disabled"`: он **никогда не делает HTTP-запрос и не
сохраняет персональные данные**. Поэтому `data-lead-endpoint` — это контрактный
маркер, а не URL действия формы.

В статическом HTML технические значения имеют безопасное наглядное
представление:

- `site_key=microchips-by` и `locale=ru-BY` — hidden-поля текущего RB-профиля;
- `page_url` — абсолютный `https://microchips.by/...` с маркером
  `data-page-url="absolute-current-route"`; в Next.js его заменяет URL
  опубликованного маршрута, а не путь из файла ТЗ;
- `cart` содержит JSON-массив, `utm` — JSON-объект; mapper декодирует их до
  отправки в API, вместо набора несвязанных полей `utm_source`, `utm_medium` и
  т. п.;
- `company` и `contact_name` обязательны. `email` и `phone` — два независимых
  поля: пользователь заполняет хотя бы одно, что соответствует
  `required_without` в `LeadController`.

В боевом интерфейсе mapper создаёт ровно объект из предыдущего раздела,
устанавливает абсолютный `page_url` из `window.location`/SSR-route, валидирует
условие «e-mail или телефон» и показывает успех только после `201`. Нельзя
добавлять в DOM или принимать от клиента внутренний `site_id`.

## Порядок реализации

1. Утвердить прототип командой `scripts/verify-rb-prototype.ps1` и визуальной
   проверкой desktop/mobile-состояний.
2. Разбить шаблон на Next-компоненты без переноса placeholder-данных в seed
   или production code.
3. Добавить server-rendered category/product listing и объявить metadata только
   из `resolve` payload.
4. Реализовать неиндексируемые filter/search routes, затем форму и локальное
   создание заявки.
5. До публикации прогнать frontend build, unit/feature lead-тест, `seo:audit`,
   sitemap/robots проверку и тестовую заявку до очереди Bitrix24.

## Статическая защита артефакта

`scripts/verify-rb-prototype.ps1` проверяет сам HTML как ТЗ: UTF-8/семантику,
`noindex`, отсутствие fake canonical, contract-markers, безопасные признаки
фильтра и поиска. Для формы он читает текущие обязательные поля из
`LeadController`, сверяет их с контролами макета, требует отдельные видимые
`company`/`contact_name`/`email`/`phone`/`message`, hidden `site_key`/`locale`,
абсолютный `page_url` и JSON-представления `cart`/`utm`. Он также запрещает
relative `page_url`, legacy-поля формы и действие, способное отправить данные.
Дополнительно проверяются отсутствие внешних изображений, fetch/XHR и
сторонних script/style resources. Это не замена SSR/e2e SEO-проверке, но
делает ошибочную публикацию или дрейф макета заметными ещё до переноса.

```powershell
./scripts/verify-rb-prototype.ps1
./scripts/verify-rb-prototype.ps1 -Path docs/prototypes/rb-b2b-catalog.html
```
