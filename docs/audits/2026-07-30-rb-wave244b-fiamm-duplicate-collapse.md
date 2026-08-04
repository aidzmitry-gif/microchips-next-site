# Wave244B: FIAMM exact duplicate collapse evidence

Дата: 2026-07-30  
Режим: fail-closed research и Laravel dry-run, без `--apply`

## Scope

Исследованы только две пары из Wave243B:

| Duplicate Bitrix | MPN | Survivor 1C |
|---|---|---|
| `bitrix:1488` | `FG21202` | `ФР-00001439` |
| `bitrix:1542` | `FG21803` | `ФР-00001513` |

Discovery ledger закреплён SHA-256
`1e1c7e1dc846cd24207009f797b3645f807e821b8772cfd297b414e638d22eba`.
Другие FIAMM/Panasonic карточки в Wave244B не рассматривались.

## Новый manufacturer-primary источник

Источник: официальный FIAMM FG catalogue, revision 04.2026:

`https://www.fiamm.com/fileadmin/user_upload/products/reserve/FG/FG_FOLDER_EN.pdf`

Snapshot SHA-256:
`544817b47e43ac6edad1d9b5e17235284de6fa65cf13f650cf37508e6fc3a9bc`.

Fail-closed no-repeat gate подтвердил:

- прежних упоминаний exact URL в audit/import artefacts: 0;
- совпадений SHA с прежними PDF в `docs/audits/sources`: 0.

На странице 2 находятся две отдельные bounded строки:

- `FG21202* 12 10,8 12 151 98 93 98 3.7 Faston 6.3`;
- `FG21803* 12 17 18 181 76 167 163 5.6 Flag Ø5.5`.

Таким образом источник подтверждает exact MPN, 12 V, ёмкости 12/18 Ah и
различные терминалы. Страница извлечена через `pdfplumber`, отрендерена Poppler
и визуально проверена: таблица, строки и footer FIAMM/Rev. 04.2026 читаемы,
clipping и перекрытия отсутствуют.

## Live DB safety

Read-only запросом проверены ровно четыре продукта. Снимок закреплён в
`docs/audits/sources/wave244b-fiamm-duplicates/live-db-safety-snapshot.json`.

Оба Bitrix duplicate:

- product status `draft`, но имеют ровно один published site product;
- availability `on_request`;
- ровно один noindex URL и closed SEO без schema;
- цена и price evidence отсутствуют;
- verified published media = 0;
- family roles = 0;
- категория `seo:batteries-ups`.

Оба 1C survivor:

- product status `active`, manufacturer `FIAMM`, exact MPN;
- ровно один published noindex site product, availability `on_request`;
- сохраняют `seo:batteries-ups` и дополнительную категорию `410`;
- `FG21202`: 85.00 BYN и ровно одно совпадающее current price evidence;
- `FG21803`: 65.50 BYN и ровно одно совпадающее current price evidence;
- нет family roles; имеющееся verified media остаётся у survivor.

Результат safety gate: PASS 2, HOLD 0. Builder требует PASS обеих строк; при
любом drift manifest не перезаписывается.

## Артефакты

- `scripts/acquire-rb-wave244b-fiamm-duplicate-source.py`;
- `scripts/build-rb-wave244b-fiamm-duplicate-collapse.py`;
- `scripts/tests/test_build_rb_wave244b_fiamm_duplicate_collapse.py`;
- `docs/audits/sources/wave244b-fiamm-duplicates/`;
- `docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse-evidence.csv`;
- `docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse.summary.json`;
- `docs/imports/rb-reviewed-fiamm-duplicates-wave244b-2026-07-30.json`.

Manifest SHA-256:
`eaba582243a805ae2aee5058003a94834451e6261f74a980eab16be93ad2b448`.

## Верификация

Python:

`python -m pytest -p no:cacheprovider scripts/tests/test_build_rb_wave244b_fiamm_duplicate_collapse.py -q`

Результат: `4 passed`.

Laravel-команда была синхронизирована в временный backend-контейнер из
текущего workspace, поскольку запущенный image содержал старую версию без
evidence-backed survivor gate. Финальный запуск выполнен без `--apply`:

```json
{
  "mode": "dry_run",
  "requested": 2,
  "collapsed": 2,
  "already_collapsed": 0,
  "redirect_purposes_repaired": 0,
  "redirect_purpose_repairs_pending": 0,
  "site_products_deleted": 0,
  "canonical_products_deleted": 0
}
```

Никакие строки БД, redirects, site products или canonical products не изменены.
`apply`, commit и push не выполнялись.
