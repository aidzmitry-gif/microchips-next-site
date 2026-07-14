# Microchips multi-market platform

Один код для четырёх независимых региональных витрин. Laravel владеет каталогом, URL, SEO, заявками и импортами; Next.js рендерит публичные страницы по домену в SSR.

## Что уже есть

- Laravel 13, Filament 5, PostgreSQL/Redis/Horizon-ready Docker-контур и Next.js 16 SSR-витрина;
- общие `products` и региональные `site_*` таблицы с обязательной изоляцией `site_id`;
- API разрешения домена и URL, каталога, sitemap и двух B2B-заявок;
- 301-реестр, self-canonical, динамические `robots.txt` и `sitemap.xml`;
- очередь для Bitrix24 и адресная invalidation Next.js после изменения контента;
- staging-команда для CSV 1С. Она не публикует товары автоматически.

Реальные домены, юридические лица, телефоны, доставка, цены и контент намеренно не зашиты в проект. Тестовые профили имеют домены `.test` и не могут служить материалом для запуска.

## Быстрый запуск в Docker

1. Скопируйте `.env.example` в `.env` и задайте сильные `POSTGRES_PASSWORD`, `LARAVEL_APP_KEY` и `NEXT_REVALIDATE_SECRET`.
2. Запустите `docker compose up --build -d`.
3. Выполните `docker compose run --rm backend php artisan migrate --seed --force`.
4. Откройте `http://localhost:3000` для витрины и `http://localhost:8080/admin` для Laravel/Filament.

Тестовый пользователь создаётся только для стенда: `admin@microchips.test`. Перед любым внешним доступом задайте `INITIAL_ADMIN_PASSWORD` и замените этот пароль. Horizon запускается только в Linux-контейнере: его `pcntl` и `posix` недоступны в Windows PHP.

## Локальная проверка

```powershell
pnpm install
pnpm --filter frontend build

# В PHP должны быть включены pdo_sqlite, sqlite3, mbstring, dom и xmlwriter.
php backend/vendor/bin/phpunit
```

## Контракты

| Endpoint | Назначение |
| --- | --- |
| `GET /api/v1/sites/{host}/resolve?path=/...` | Возвращает только контент этого домена либо структурированный redirect/not_found. |
| `GET /api/v1/sites/{site}/catalog/products` | Отдаёт только опубликованные товары конкретного рынка. |
| `GET /api/v1/sites/{host}/seo/sitemap` | Источник URL для sitemap конкретного домена. |
| `POST /api/v1/leads/quote` | Сохраняет `site_id`, locale, UTM, URL и корзину до постановки Bitrix24-задачи в очередь. |
| `POST /api/v1/leads/battery-pack-design` | Та же трассируемость для запроса разработки аккумуляторной сборки. |

## Ограничения запуска

Ни один регион не готов к индексации, пока не заполнены подтверждённые коммерческие и юридические данные и не пройден чек-лист из [SEO migration checklist](docs/seo-migration-checklist.md). Не добавляйте IP-редиректы, коммерческие `Offer` без подтверждённой цены и остатка, либо тонкие city-страницы.

Для настоящего миграционного аудита нужны архив веб-каталога Bitrix и дамп БД. Найденный `admin.*.tar` — Hestia admin backup без `web/` и дампа сайта, поэтому не является таким источником.

Подробный текущий статус — в [implementation status](docs/implementation-status.md), а безопасный контракт 1С — в [data-import-contract.md](docs/data-import-contract.md).
