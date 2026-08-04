# RB industrial catalog — Wave 201

Дата: 2026-07-29  
Рынок: Беларусь (`microchips-by`)  
Статус: завершён безопасный подготовительный и duplicate-collapse этап; неподтверждённые характеристики не публиковались.

## Результат цикла

- Очередь из 500 приоритетных B2B-карточек разбита на проверяемые партии без повторной обработки уже закрытых серий: 249 назначено в пять OEM/model-core партий, 251 оставлена в следующей очереди.
- Проверены 12 текущих Cameron Sino карточек, представляющих восемь уникальных моделей. Первичные и вторичные источники не дали достаточного непротиворечивого набора характеристик для массового обогащения, поэтому описания, цены, наличие, MPN и изображения не изменялись.
- Один строгий дубль `CS-MC90BX 7.4V 3400mAh` (`bitrix:24052`) свёрнут в `bitrix:12149`. Удалена только дублирующая региональная публикация; общая запись Product сохранена. Старый URL отдаёт постоянный redirect на survivor.
- Две пары `CS-MC950BL` не свёрнуты: в исходных карточках заявлены разные ёмкости `4600` и `7010 mAh`, а официальный документ подтверждает только модель и напряжение. Шесть остальных записей также оставлены в hold.

## Подготовленная массовая очередь

Источник: `docs/audits/generated/wave201-industrial-preparation-summary.json`.

| Партия | Карточек |
|---|---:|
| Zebra / Motorola / Symbol | 151 |
| Honeywell | 42 |
| Datalogic | 26 |
| Intermec | 18 |
| Cameron Sino exact model | 12 |
| Нераспределённый остаток | 251 |

OEM-документы Zebra/Honeywell/Datalogic/Intermec считаются доказательством совместимости устройства, но не автоматически производителем или MPN сменной батареи. Это ограничение сохранено для следующего массового этапа.

## Источники Cameron Sino и решения

- `CS-DAV200BL`, `CS-ICN700BX`: официальный документ Cameron Sino подтверждает модель и `3.7 V`; ёмкость из вторичного магазина не переносилась.
- `CS-MC950BL`: официальный документ Cameron Sino подтверждает модель и `3.7 V`, но не разрешает конфликт ёмкостей.
- `CS-DKA300BX`: вторичный источник указывает `4 V`, тогда как legacy-карточка содержит `3.7 V`; hold.
- `CS-ET4090BX`: вторичный источник указывает `4400 mAh`, legacy-карточка — `2330 mAh`; hold.
- `CS-ZQN420BX`: вторичный источник указывает `7.4 V / 5200 mAh`, но первичного точного источника нет; hold.
- `CS-MBE500BL`: точный источник не найден; hold.

Реестр доказательств: `docs/audits/generated/wave201-cameron-sino-source-registry.csv`.  
Реестр hold: `docs/audits/generated/wave201-cameron-sino-holds.csv`.  
Adversarial partition: `docs/audits/generated/wave201-cameron-sino-duplicate-partition.csv`, SHA-256 `0A1D065A5E0BD1FB361D731CEA537804BB95F179847EC366D562AF7602A8EF6E`.

## Защитный механизм дублей

Добавлена manifest-driven команда:

```text
catalog:collapse-verified-noindex-duplicates {site} {file} [--apply]
```

Она fail-closed проверяет точные имена, URL, bounded model core, напряжение, ёмкость, категории, отсутствие цены/ценового доказательства, проверенного media, family-role и индексируемого SEO. Команда создаёт только preview-purpose permanent redirect и удаляет только `SiteUrl`, `SiteSeo`, `SiteProduct` дубля. Shared Product и другие рынки не затрагиваются.

Применён manifest `docs/imports/rb-reviewed-noindex-duplicates-cameron-sino-wave201-2026-07-29.json`. Повторный dry-run подтвердил идемпотентность:

```json
{
  "requested": 1,
  "collapsed": 0,
  "already_collapsed": 1,
  "site_products_deleted": 0,
  "canonical_products_deleted": 0
}
```

## Исправление runtime redirect

Локальный redirect-proxy использовал hostname `localhost`, тогда как основной page resolver использовал `DEFAULT_SITE_HOST=microchips-by.test`. Из-за расхождения backend 301 обходился, а Next.js выдавал временный 307. `frontend/src/proxy.ts` теперь применяет тот же локальный site-profile до redirect lookup.

Runtime после пересборки:

- `/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-24052` → **301** на survivor;
- `/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12149` → **200**, содержит `CS-MC90BX`, остаётся `noindex`.

## Верификация

- `python -m pytest -q -p no:cacheprovider scripts/tests/test_build_rb_wave201_industrial_preparation.py scripts/tests/test_wave201_cameron_sino_evidence.py` — **4 passed**.
- `CollapseVerifiedNoindexDuplicatesTest.php` — **2 tests, 19 assertions passed** в dev-test контейнере; production image ожидаемо не содержит Artisan `test` runner.
- `npm test -- --run src/proxy.test.ts` — **6 passed**.
- `docker compose build frontend` — Next.js production build и TypeScript — **passed**.
- `php artisan seo:audit microchips-by --json` — **passed**, 16 857 URL, 93 redirect, 0 блокеров.
- Runtime HTTP — duplicate **301**, survivor **200**.

## Готовность

Цикл повысил проверенное качество дедупликации и миграционных редиректов, но не пересекает следующий общий порог готовности. Подтверждённая готовность проекта остаётся **60%**. Следующий прирост должен идти из массовой обработки назначенных 151 + 42 + 26 + 18 OEM-совместимых B2B-карточек с сохранением source-boundary.
