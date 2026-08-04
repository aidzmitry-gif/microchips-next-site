# RB: browser regression и local inbox без Bitrix24

Дата: 2026-07-26. Ветка: `codex/readiness-80-loop`.

## Решение

Для первого запуска Беларуси Bitrix24 не является обязательной зависимостью.
Заявка сохраняется в локальной таблице `leads` и обрабатывается оператором в
Filament `/admin/leads`. CRM-интеграция остаётся опциональным site-scoped
адаптером: задача синхронизации ставится в очередь только когда оператор
явно включил Bitrix24 для конкретного сайта.

Такой режим не маскирует отсутствие CRM: в preflight вместо «успешного лида
Bitrix24» требуется реальный обработанный оператором local-inbox lead на
staging. Внешние DNS/TLS, кабинеты вебмастеров, indexability и 14-дневное
наблюдение остаются отдельными обязательными доказательствами запуска.

## Закрытый критерий: automated regression tests (15% readiness РБ)

Добавлен один fixture-driven Laravel gate и browser E2E для production
standalone Next.js:

- `RbLaunchRegressionGateTest` импортирует RB fixtures, проверяет 7 contacts
  и 5 commercial facts, отсутствие утечки в `not_found`, безопасный noindex
  продукт без цены/`Offer` и сохранение site-/locale-bound заявки в local inbox;
- Playwright поднимает локальный mock Laravel API и фактический standalone
  frontend; проверяет SSR catalog desktop/mobile, длинное реальное название,
  `noindex`, schema без `Offer`, отсутствие горизонтального скролла, мобильное
  меню и успешный POST формы;
- workflow GitHub Actions устанавливает Chromium и выполняет E2E после
  production build; diagnostics сохраняются artifact-ом только при ошибке.

Локальная проверка: `pnpm --filter frontend test:e2e` — **3 passed, 1 skipped**
(desktop-check намеренно пропускается в mobile-only сценарии). Production build
до E2E прошёл. PHP CLI на рабочей машине не содержит `mbstring`, поэтому
локальный повтор всего PHPUnit этим бинарником не является валидным evidence;
изменённые PHP-файлы требуют прохода CI/контейнера разработки с dev dependencies.

## Пересчёт готовности

Часть 5 (Беларусь):

```text
25% local commercial/legal data  = complete
15% automated regression tests  = complete
30% SEO/GEO and localized pages  = not complete
20% catalog and local-inbox flow = not complete (23 draft products < Gate 0: 50)
10% monitoring and launch check  = not complete
```

`40% × 15% = 6,0%` общего плана; части 1–4 дают `45,0%`. Подтверждённый
итог: **51,0%**. До 60% нельзя честно засчитать ещё 9 пунктов: внешние
доказательства и минимум 50 утверждённых продуктов не подменяются кодом.
