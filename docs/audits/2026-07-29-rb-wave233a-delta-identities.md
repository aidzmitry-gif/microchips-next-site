# Wave233-A — Delta: локально подтверждённые OEM identity

Дата проверки: 2026-07-29.

## Граница

Из `docs/audits/generated/rb-wave233-identity-media-gaps.csv` отобраны ровно
152 уникальные карточки `seo:batteries-ups` с пустым `manufacturer`, чьё имя
начинается с `Аккумулятор Delta`. MPN извлекается только из ограниченного
фрагмента имени между `Аккумулятор Delta ` и ` (AGM,`; все 152 названия ему
соответствуют, а после нормализации MPN не повторяются.

Сеть не использовалась. Источник доказательств — уже сохранённые официальные
Delta snapshots, привязанные хешами в registry Wave198/Wave206/Wave211b. Для
PASS builder дополнительно проверяет SHA-256 snapshot и наличие exact
normalised MPN в его содержимом. Ни медиа, ни цена, ни остаток не меняются.

## Решение

| Результат | Карточек |
| --- | ---: |
| PASS | 16 |
| HOLD | 136 |
| HOLD: нет локального официального exact-MPN evidence | 120 |
| HOLD: canonical MPN/SKU conflict | 23 |

Причины HOLD могут пересекаться: 7 карточек одновременно не имеют пригодного
локального source и имеют canonical conflict. Срез канонических коллизий снят
read-only запросом Products 2026-07-29; любое совпадение normalized MPN или
SKU с другим `Product` — безусловный HOLD. В том числе удержаны совпадения с
другим производителем, поскольку это не доказательство отсутствия коллизии.

В manifest включены только 16 PASS. Он соответствует schema v1 существующей
`catalog:apply-verified-oem-identities`: каждая строка содержит оба поля,
`manufacturer=Delta` и точный `mpn`, плюс HTTPS URL и SHA-256-pinned snapshot.
Команда не является manufacturer-only allowlist: она требует непустой `mpn` и
при apply заполняет blank manufacturer **и** MPN. Поэтому для применения этого
PASS manifest код команды менять не нужно, но применять его как
manufacturer-only manifest без изменения команды нельзя.

## Артефакты и проверка

- Manifest: `docs/imports/rb-delta-identity-stage-manifest-wave233a-2026-07-29.json`
- Полный ledger (152, включая HOLD): `docs/audits/generated/rb-wave233a-delta-identity-ledger.csv`
- Summary: `docs/audits/generated/rb-wave233a-delta-identity-summary.json`
- Rebuild: `python scripts/build-rb-wave233a-delta-identities.py`
- Проверка: `python scripts/tests/test_build_rb_wave233a_delta_identities.py`

Проверка builder/test завершена успешно. DB apply и dry-run apply не выполнялись.
