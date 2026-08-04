# Wave250 — аудит provenance для 403 B2B-карточек

Дата: 2026-07-30  
Режим: read-only, без сети, без изменений БД и без публикации.

## Результат

- Проверены ровно 403 B2B-карточки, которые Wave249 исключил из-за пустого или недопустимого description provenance.
- Проверены 223 уже закреплённых JSON/CSV-артефакта из Wave246; каждый вход повторно подтверждён по SHA-256.
- Безопасных детерминированных relink-кандидатов: **0**.
- Конфликтующих детерминированных решений: **0**.
- В fail-closed очереди на исследование источника остаются: **403**.
- Причина для всех 403: `NO_PINNED_ARTIFACT_WITH_COMPLETE_ALLOWED_PROVENANCE_AND_CURRENT_IDENTITY`.

Наличие URL или текста в старом артефакте не считалось достаточным. Relink разрешался только при одновременном выполнении условий:

1. точный `product_external_id`;
2. тот же HTTPS `source_url`, что и в recovery manifest;
3. допустимая пара `source_kind` / `source_tier`;
4. `identity_scope` только `exact` или `model_core`;
5. совпадение производителя и MPN либо полное Unicode-boundary совпадение model core;
6. SHA-256 исходного evidence-артефакта совпадает с закреплённым значением.

## Приоритет очереди

Приоритет задан только объёмом блокеров одного нормализованного производителя, чтобы следующий проход дал максимальный результат и не повторял уже проверенные карточки:

| Приоритет | Правило | Карточек |
|---|---:|---:|
| P1 | 20 и более блокеров производителя | 318 |
| P2 | 5–19 блокеров | 57 |
| P3 | менее 5 блокеров | 28 |

Крупнейшие группы: EnerSys — 213, LEOCH — 55, CSB — 29, Exide — 21, Delta — 17, MEAN WELL — 13, FIAMM — 9, APC — 7, B.B. Battery — 6, Zebra — 5.

## Артефакты

- `docs/audits/generated/rb-wave250-description-provenance-relink-2026-07-30.json` — доказательный manifest и manufacturer summary.
- `docs/audits/generated/rb-wave250-description-provenance-relink-2026-07-30.csv` — все 403 решения; SHA-256 `eeec3867b88b31bd7fadb4b40855f76f9a0909d85928dcd92811dfc4e5004903`.
- `docs/audits/generated/rb-wave250-description-source-research-queue-2026-07-30.csv` — приоритетная очередь; SHA-256 `9a9889d68ca8c6d6b974efa696b16ac4d6bc1438e2130d85b98545b5a9d93892`.
- Recovery manifest pin: `be27aa0b4f672334b95002d2a96cfedb2b198c893b3d1a0ce5e385681da40923`.

Generated-артефакты остаются локальными и исключены `.gitignore`; они воспроизводятся скриптом.

## Верификация

```text
python -m pytest scripts/tests/test_build_rb_wave250_description_provenance_relink.py -q -p no:cacheprovider
3 passed

python -m py_compile scripts/build-rb-wave250-description-provenance-relink.py scripts/tests/test_build_rb_wave250_description_provenance_relink.py
PASS

python scripts/build-rb-wave250-description-provenance-relink.py
audited=403; safe_deterministic_relinks=0; research_required=403; conflicts=0
network_requests=0; database_mutations=0
```

Никаких relink/apply действий не выполнено. Следующий отдельный research-проход должен начинаться с P1 и использовать готовый `no_repeat_basis`, а не повторно сканировать уже закреплённые артефакты.
