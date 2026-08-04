# Wave206 — Panasonic, Ventura и MNB

Дата проверки: 2026-07-29. Область: ровно 85 B2B-позиций из `rb-b2b-next-source-batch-wave205.csv`: Panasonic — 34, Ventura — 28, MNB — 23.

## Результат

| Решение | Количество | Действие |
|---|---:|---|
| `exact_safe` | 29 | Идентичность и базовые характеристики подтверждены первичным каталогом |
| `compatibility` | 5 | Модель подтверждена, но заявленная ёмкость не доказана watt-rated таблицей HR/HRL |
| `conflict` | 5 | Данные старого названия противоречат текущему каталогу Ventura |
| `no_evidence` | 46 | Модель отсутствует в закреплённом текущем первичном каталоге |

Из 29 точных идентичностей автоматически применимы 25. `bitrix:1466` (`Ventura GPL 12-120`, AGM) удержан: в полном реестре есть `bitrix:1467` с тем же manufacturer+model, но ошибочным GEL-названием. Current PostgreSQL collision guard дополнительно удержал `bitrix:1457`, `bitrix:1516` и `bitrix:1563`: их нормализованные MPN уже принадлежат активным 1С-товарам `КА-00003397`, `КА-00003228` и `КА-00003696`.

## Существенные конфликты

- Ventura FT 12-100, FT 12-150 и FT 12-180: старые названия утверждают GEL, официальный каталог — AGM.
- Ventura FT 12-125: официальный каталог указывает AGM и 130 А·ч, старое название — GEL и 125 А·ч.
- Ventura GPL 12-120 `bitrix:1467`: старое название утверждает GEL, официальный каталог — AGM.
- Ventura HR/HRL (5 строк): официальный каталог подтверждает модель, 12 В и AGM, но приводит мощность в ваттах, а не заявленную старым названием ёмкость в А·ч. Ёмкость не перенесена.

## Первичные снимки

- Panasonic Industry VRLA Handbook — SHA-256 `93785723bfcab8f21a7df198673be9886bc220aabd15486a2afca4d01d1f3a42`.
- Ventura Catalogue 2023 — SHA-256 `68d09cc1255c5b8fbec04c669701ca21616ae501484d043dbc6fb512ae3ea839`.
- MNB Battery official catalogue — SHA-256 `85dac18f2953eeb29e306434b0af658a49f96afcc04d182ea2a2b8ef7b207859`.

PDF и извлечённый текст закреплены отдельными SHA-256 в `docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json`. Выходной evidence: `docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv`.

Laravel-манифест содержит ровно те же 25 ID, что и строки `safe_to_apply=true` в CSV. Неизменённая команда `catalog:apply-verified-oem-identities` прошла dry-run: 25 записей, exit code 0, manifest SHA-256 `73bfc5abd4649ec4b2c5982ee78b2508f3ce1e0fc9d8ca2cf7af7d9421dd6d0a`. База не изменялась.

## Защитные ограничения

- Цена, остаток, изображение, публикация и индексируемость этой волной не разрешены.
- `compatibility`, `conflict` и `no_evidence` не получают manufacturer/MPN для применения.
- Проверка дублей выполнена по полному реестру из 17 207 строк.
- Перед Laravel-манифестом выполнена read-only проверка текущей PostgreSQL через `ProductIdentity::normalize`: 3 из 28 предварительно безопасных строк имеют живую SKU/MPN-коллизию и исключены.
- Адверсариальная проверка исключила ложный дубль MNB `MS 1.2-6 F1` ↔ `MS 12-6 F1`: десятичная точка теперь является значимой частью identity-key.
- Изменений базы данных, коммитов и push нет.

## Верификация

`python -m pytest scripts/tests/test_wave206_panasonic_ventura_mnb_evidence.py -q -p no:cacheprovider` → `6 passed`.

`php artisan catalog:apply-verified-oem-identities microchips-by <manifest>` без `--apply` → 25/25 записей, exit code 0.
