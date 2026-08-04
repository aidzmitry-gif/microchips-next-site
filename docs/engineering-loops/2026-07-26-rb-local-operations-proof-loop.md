# RB local operations proof loop — 2026-07-26

## Назначение

Подтвердить локальный эксплуатационный контур Беларуси без Bitrix24 и без
открытия товарных URL для индексации.

## Проверки

1. В рабочем Docker PostgreSQL создан custom-format backup.
2. Архив восстановлен `pg_restore` в отдельную временную БД.
3. Проверены таблица `migrations` и минимум одна запись в `users`.
4. Временная БД и архив удалены runner-ом после успеха.
5. `GET /api/v1/sites/microchips-by.test/resolve?path=/contacts` вернул
   опубликованную noindex-страницу и подтверждённый RB commercial profile.
6. Тот же resolver для `/catalog` вернул `not_found`.
7. `seo:audit microchips-by --json` завершился без blocking issues:
   5 проверенных URL, 0 sitemap URL, 0 blockers.

## Контроль публикации

Команда `site:publish-commercial-pages-package` принимает только четыре
страницы: `contacts`, `delivery`, `payment`, `warranty`. Перед изменением
она требует для каждой соответствующие noindex `SiteUrl` и `SiteSeo`.
Она не меняет товары, категории, цены, sitemap или индексируемость.

На текущем RB-профиле все четыре страницы уже были опубликованы как noindex;
dry-run и apply подтвердили идемпотентное состояние. В базе также есть семь
опубликованных и верифицированных контактов и пять опубликованных
верифицированных коммерческих фактов.

## Граница доказательства

Это не запуск страны: нет внешнего staging DNS/TLS, search-console/webmaster
верификаций, внешнего crawl и разрешения 93 source findings. Поэтому
товарные URL остаются закрытыми, а готовность не повышается автоматически.
