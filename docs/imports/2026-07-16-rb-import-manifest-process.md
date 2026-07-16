# RB import manifest: процесс заполнения и гейт публикации

## Что это

Черновик import-манифеста для первой RB-очереди (фокус ИБП/резервное питание,
**1 569 кандидатов** по scope correction аудита
`docs/audits/2026-07-14-b2b-catalog-slice.md`: 1 445 по primary-пути + 124
через дополнительную привязку секций). Манифест превращает блокер
идентичности («у всех 2 856 записей нет артикула») в конкретную задачу
заполнения для бизнеса.

## Как воспроизвести

```powershell
# 1. Срез из read-only бэкапа (если evidence ещё не сгенерирован)
./scripts/extract-bitrix-b2b-catalog-slice.ps1 -SourceRoot "D:\6 Проекты\microchips.by"

# 2. Черновик манифеста
./scripts/build-rb-import-manifest.ps1
```

Выход (в игнорируемой `docs/audits/generated/`):

- `rb-import-manifest-draft.csv` — 1 569 строк;
- `rb-import-manifest-summary.json` — контрольные суммы.

Генератор детерминированный и падает, если счётчики фокуса расходятся с
аудитом (1 569 / 1 445 / 124).

## Что заполняется автоматически (инженерная часть)

| Колонка | Источник |
| --- | --- |
| `focus_reason`, `focus_section_path` | принадлежность фокусу по аудиту |
| `capacity/voltage/technology_from_name` | сигналы только из явного текста названия |
| `quality_issue_codes`, `duplicate_name_count`, `has_media_reference` | quality-срез |
| `series_hint_key`, `series_hint_size` | группировка названий, отличающихся только числами (240 групп, 1 320 строк) — вход для шаблона «страница серии» (М3 в ТЗ) |
| `proposed_shared_category` | akb-dlya-ibp (1 097) / ibp-ustroystva (337) / akb-rezervnoe-pitanie (135) |
| `proposed_disposition` | `exclude_inactive_candidate` (6 неактивных) / `import_candidate_pending_identity` |

## Что должен заполнить бизнес (колонки пустые намеренно)

- `supplier_or_1c_id` — стабильный идентификатор из 1С или прайса поставщика;
- `sku` / `mpn` — где существуют;
- `approved_category` — подтверждение или правка предложенной категории;
- `final_disposition` — `import` / `merge_into_series` / `skip` + причина в
  `review_note`;
- `reviewer` — кто принял решение.

Достаточно начать с репрезентативной выборки 30–50 строк — этого хватит для
первого staging-прогона импорта.

## Гейт (неизменяемый)

Публикация и автоматическое сопоставление общего каталога **заблокированы**,
пока у строки не заполнена идентичность и `review_status` ≠ `approved`.
Манифест не создаёт товары, URL и редиректы сам по себе; решения по legacy
URL остаются в URL-реестре (см. registry-документы). Рабочие реквизиты
компании в прототипах — отдельный трек (память проекта:
`rb-requisites-are-example`), финальная сверка перед запуском.
