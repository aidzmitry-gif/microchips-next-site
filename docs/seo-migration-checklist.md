# SEO migration checklist

## Deterministic registry generation

Generate the local, ignored decision registry only after regenerating the raw inventories:

```powershell
.\scripts\build-legacy-url-decision-registry.ps1
```

The command writes `docs/audits/generated/legacy-url-decision-registry.csv` and
`legacy-url-decision-summary.json`. It assigns only evidence-based `keep`, `fix`,
`redirect`, or `remove` decisions plus `needs_review`/`blocker` status. `final_url`
is deliberately empty in every generated row: no legacy target is copied or invented
as a new redirect destination. Run the embedded deterministic checks with:

```powershell
.\scripts\build-legacy-url-decision-registry.ps1 -RunSelfTest
```

## До импорта

- Получен полный crawl старого сайта и URL registry: `old_url`, page type, priority, keep/fix/redirect/remove, final URL и owner.
- Зафиксированы HTTP status, title, H1, canonical, robots, schema, content, image и internal links для priority URLs.
- Утверждены исключения: фильтры, сортировки, поиск и tracking parameters не становятся indexable URL.

## До запуска каждого домена

- Указаны реальные юрлицо, адрес, телефоны, почта, доставка, оплата, гарантия/сервис и локальная аналитика.
- Все canonical URL self-referential и не ведут в другую страну.
- Есть отдельные Search Console, Yandex Webmaster, analytics property, sitemap и `robots.txt`.
- Эквивалентные, реально локализованные страницы связаны reciprocal `hreflang`: `ru-BY`, `ru-RU`, `ru-UZ`; для Узбекистана — также `uz-UZ`.
- Schema `Organization`/`LocalBusiness` содержит только подтверждённые данные; `Offer` выводится только с проверенной локальной коммерческой информацией.
- Нет IP-редиректов, thin city pages, redirect chains, home-page redirects для удалённых URL и soft-404 с HTTP 200.

## Беларусь: cutover blocker

- 100% priority legacy URL имеют финальное решение и single-hop 301 там, где это нужно.
- Прошёл automated и ручной old-vs-new regression report.
- На staging протестированы sitemap, robots, canonical, заявки и восстановление резервной копии.
- После запуска 14 дней отслеживаются crawl errors, 404, цепочки, CWV, leads и CRM delivery.
