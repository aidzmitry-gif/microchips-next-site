# RB official content and dedup — Wave 118

## Результат

- Два параллельных исследования сгруппировали Robiton и элементы питания по
  точной модели и исключили уже обработанные карточки.
- Применено 19 новых описаний только из первичных источников производителей:
  12 Robiton, 5 Energizer и 2 Panasonic.
- Исключены две неопубликованные копии Robiton: `КА-00002302` в пользу
  `КА-00004406` (IR12-2000S) и `ФР-00001813` в пользу `ФР-00001866`
  (ProCharger1000).
- 1С-варианты с разъёмами, выводами, упаковкой или конфликтующей ёмкостью
  оставлены на hold и не объединялись.
- Фото не импортировались: наличие изображения на странице производителя не
  является разрешением на локальное копирование.

## Проверки

| Проверка | Результат |
|---|---|
| Robiton description staging dry-run | 12 created, 0 unchanged, 0 published |
| Robiton descriptions applied | 12 applied, 0 commercial changes |
| Cells description staging dry-run | 7 created, 0 unchanged, 0 published |
| Cells descriptions applied | 7 applied, 0 commercial changes |
| Duplicate exclusion dry-run | 2/2 non-public links valid |
| Duplicate exclusion apply | 2 links removed, 0 canonical products deleted |
| Batch triage tests | 5 passed |

## Изменение очереди

- eligible site products: 5 701 → 5 699;
- новые кластеры без готового описания: 101 → 83;
- строго готовые карточки: 44/7 286 (0,60%), без изменения.

Строгий процент не вырос, потому что формула требует одновременно применённое
описание и проверенное опубликованное изображение. Контентный долг уменьшен на
19 карточек; следующий рост строгого процента зависит от собственного или
разрешённого медиаконтента, а не от повторного написания описаний.

## Артефакты

- `docs/imports/rb-strict-duplicate-exclusion-robiton-wave-118.csv`
- `docs/imports/rb-source-backed-description-drafts-robiton-wave-118-2026-07-28.json`
- `docs/imports/rb-source-backed-description-drafts-cells-wave-118-2026-07-28.json`
- `docs/audits/generated/rb-enrichment-queue-wave-118-post.csv`
- `docs/audits/generated/rb-batch-catalog-triage-wave-118-post-summary.json`
