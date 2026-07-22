# Гейт кандидатов 1С ↔ Bitrix для ручной проверки

`scripts/build-rb-1c-review-queue.py` создаёт воспроизводимую очередь **кандидатов на ручную проверку** из `rb-1c-match-v2-matched.csv`. Результат не является подтверждением идентичности, разрешением публикации или импортом.

## Правило отбора

Строка попадает в очередь только при одновременном выполнении условий:

- `confidence` численно равно `0.95`;
- `brand_ok` равно `yes` без учёта регистра;
- `method` не содержит `generic`;
- заполнены `Bitrix ID` и `1С-код`;
- один `1С-код` указывает ровно на один `Bitrix ID`;
- один `Bitrix ID` указывает ровно на один `1С-код`;
- пара `Bitrix ID` + `1С-код` встречается во входе ровно один раз.

Последние два условия не доказывают правильность матча, а только не позволяют дублям и противоречивым связям попасть в очередь.

## Запуск

```powershell
python ".\scripts\build-rb-1c-review-queue.py" --self-test
python ".\scripts\build-rb-1c-review-queue.py"
python ".\scripts\build-rb-1c-review-queue.py" --check
```

Результаты:

- `docs/imports/rb-1c-review-candidates.csv` — только `review_candidate`, каждая строка требует решения человека;
- `docs/imports/rb-1c-review-exclusions.csv` — исключённые строки с одной или несколькими причинами в `exclusion_reasons`.

`--check` ничего не перегенерирует: он пересчитывает ожидаемое содержимое и падает, если выходные CSV отсутствуют, устарели или были отредактированы вручную.

## Причины исключения

- `missing_bitrix_id`, `missing_1c_code`;
- `confidence_not_0_95`, `brand_not_confirmed`, `generic_match_method`;
- `one_c_code_maps_multiple_bitrix_ids`;
- `bitrix_id_maps_multiple_1c_codes`;
- `duplicate_source_pair`.

Очередь нельзя передавать в staging/import напрямую. Для каждой строки сначала нужны сверка с исходной карточкой 1С/поставщика и явное решение оператора в отдельном процессе review.
