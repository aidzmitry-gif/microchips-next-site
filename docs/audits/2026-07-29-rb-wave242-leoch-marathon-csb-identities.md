# Wave242: Leoch / Marathon / CSB — новые manufacturer-primary identity evidence

Дата проверки: `2026-07-29`  
Контур: `microchips-by`  
Исходная очередь: `docs/audits/generated/rb-wave241c-reviewed-identity-skips.csv`

## Результат

Проверен замороженный scope из **131** identity HOLD: CSB — 32, Leoch — 50, Marathon — 49.

| Производитель | PASS | HOLD | Всего |
|---|---:|---:|---:|
| CSB | 16 | 16 | 32 |
| Leoch | 0 | 50 | 50 |
| Marathon | 41 | 8 | 49 |
| **Итого** | **57** | **74** | **131** |

Для 57 строгих PASS созданы одновременно identity manifest и source-backed description manifest. В manifests нет HOLD-строк.

## Новые источники и правило no-repeat

Wave233c ledger зафиксирован как входной baseline с SHA-256
`836d44056c27c5ff14326d669bc1110839fc125973424dd08b3d51af24215ca6`.
Источники Wave233c повторно не использовались. Wave242 оценивает только новые сохранённые manufacturer-primary документы:

- CSB Catalog 2026 — официальный текущий каталог CSB;
- Exide Marathon L/XL — официальный технический каталог типов, напряжений, ёмкостей и UL 94-V0 вариантов;
- Exide Marathon M-FT — официальный технический каталог типов, напряжений, ёмкостей и UL 94-V0 вариантов;
- две официальные архивные спецификации Exide — использованы только для fail-closed проверки снятых типов;
- Leoch VRLA-AGM 2026 — официальный текущий каталог Leoch.

Все шесть PDF сохранены в `docs/audits/sources/wave242-leoch-marathon-csb/`. Их SHA-256 закреплены в builder и summary. Builder падает при drift любого снимка.

## PASS gate

Строка проходит только при одновременном выполнении условий:

1. точный тип присутствует в новом официальном manufacturer-primary PDF;
2. предлагаемое напряжение совпадает с таблицей;
3. предлагаемая ёмкость совпадает с одной из документированных номинальных ёмкостей или отличается не более чем на 5% из-за другого стандартного rate/округления;
4. suffix доказан документом: для Marathon `V0` принят только там, где PDF прямо говорит, что таблица действительна для UL 94-V0 версии; для CSB `F2` принят только для строк таблицы с `F1/F2`;
5. нет normalized manufacturer+MPN collision.

PASS partitions:

- `pass_exact_primary_model_capacity_voltage` — 37;
- `pass_exact_primary_model_capacity_voltage_v0` — 20.

## Почему 74 строки остались HOLD

| Partition | Строк |
|---|---:|
| `hold_no_new_exact_primary_source` | 49 |
| `hold_exact_suffix_not_proven` | 11 |
| `hold_capacity_or_v0_variant_not_proven` | 6 |
| `hold_ah_capacity_not_proven` | 3 |
| `hold_exact_model_not_in_current_catalogue` | 2 |
| `hold_normalized_mpn_collision` | 2 |
| `hold_v0_suffix_not_proven_by_exact_source` | 1 |

Ключевые fail-closed решения:

- текущий Leoch catalog использует LP/LPL/LPF/LPC/LCP nomenclature и не подтверждает старые предложенные DJW/DJM/FT модели; две строки `FT12-40` дополнительно остаются collision HOLD;
- CSB HR/HRL таблицы задают мощность в ваттах, поэтому предложенные Ah значения не считаются подтверждёнными без отдельного точного datasheet;
- suffix `FR` / `F2FR` не выводится из base-модели;
- архивные Exide строки `M12V40(F)`, `M12V70(F)`, `M12V90(F)` и `M12V180FT` не превращаются в PASS без строгой записи предлагаемого V0-варианта и проверяемой номинальной ёмкости в том же evidence chain;
- текущий CSB TPL catalog содержит SKU, отличные от предложенных `TPL121250` и `TPL121500`.

## Визуальная и автоматическая проверка

Визуально отрендерены и проверены доказательные страницы:

- CSB pages 3–4: GP/GPL model, voltage, Ah и terminal columns читаемы и выровнены;
- Exide Marathon L/XL page 4: exact type rows и UL 94-V0 clause читаемы;
- Exide Marathon M-FT page 4: exact type rows и UL 94-V0 clause читаемы;
- Leoch cover: publisher, publication number и текущие серии читаемы.

Автоматически проверено, включая реальные Laravel allowlists обеих staging-команд:

```text
python scripts/build-rb-wave242-leoch-marathon-csb-identities.py
=> rows=131, pass=57, hold=74

python -m pytest -q scripts/tests/test_build_rb_wave242_leoch_marathon_csb_identities.py
=> 4 passed
```

Identity rows содержат только поля allowlist `ApplyVerifiedOemIdentities`; `evidence_scope` в identity manifest не переносится. Description rows содержат только поля exact manufacturer-primary allowlist `DescriptionSourceEvidencePolicy`; SHA-снимки остаются закреплены в builder/summary и обязательном identity evidence, но не переносятся в description manifest. Для description staging scope всегда `identity_scope=exact`, `evidence_scope=exact_model`.

Повторный builder run даёт байт-в-байт одинаковые ledger, summary и оба manifests. Apply/commit не выполнялись.

### Реальные Laravel dry-run

Оба manifests дополнительно проверены не только Python-тестом, но и актуальными Artisan-командами в рабочем backend-контейнере. Флаг `--apply` не использовался.

```text
php artisan catalog:apply-verified-oem-identities microchips-by \
  /tmp/wave242/docs/imports/rb-verified-oem-identities-wave242-leoch-marathon-csb-2026-07-29.json

mode: dry_run
records: 57
manifest_sha256: e96799d57654575cbbf8acb4578918d50b385471bc2f3e1d358eeb75504967f0
identities_filled: 0
commercial_fields_changed: 0
publication_fields_changed: 0
exit: 0

php artisan content:stage-source-backed-description-drafts microchips-by \
  /tmp/wave242/docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json

Source-backed description run 1051: 0 created, 0 refreshed, 57 unchanged; none were published.
exit: 0
```

Финальные SHA-256:

- identity manifest: `e96799d57654575cbbf8acb4578918d50b385471bc2f3e1d358eeb75504967f0`;
- description manifest: `387348f7c54a5ed31f0e002ce6f383088afdbf048f20e7daf07c018c7d5b7e32`;
- full ledger: `448cbd79a161abff3e30f6927433ddd9e1e655ec37f942b781177ec8d65794e0`;
- summary: `dbd8ffd655517fafb79bad8ceb9d61e70c397d9b74b0add15aa468eabe043ca0`.

## Артефакты

- `scripts/build-rb-wave242-leoch-marathon-csb-identities.py`
- `scripts/tests/test_build_rb_wave242_leoch_marathon_csb_identities.py`
- `docs/audits/generated/rb-wave242-leoch-marathon-csb-identity-ledger.csv`
- `docs/audits/generated/rb-wave242-leoch-marathon-csb-identity.summary.json`
- `docs/imports/rb-verified-oem-identities-wave242-leoch-marathon-csb-2026-07-29.json`
- `docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json`
