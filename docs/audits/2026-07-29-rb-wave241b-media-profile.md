# Wave241B: полный no-repeat профиль media gap

Дата проверки: 2026-07-29.

## Scope

Зафиксированы все 745 строк `rb-enrichment-queue-wave240.csv`, для которых одновременно:

- `has_applied_description=true`;
- `has_verified_published_image=false`.

## Результат

- Exact media PASS: **0**. Promotion manifest не создавался.
- No-repeat исключения по media ledgers Wave225-240: **116** (112 всё ещё имеют локальные staging bytes, 4 уже не имеют текущего локального staging asset).
- HOLD / acquisition: **629**.
  - 407 manufacturer-synthetic строк: нужен exact официальный raster и документированные reusable rights.
  - 68 Bitrix строк: после no-repeat union отсутствует новый company-owned legacy asset.
  - 154 строки 1C/прочих namespaces: отсутствует локальный либо rights-documented официальный asset.

No-repeat union содержит 878 external ID и 595 SHA-256. Ни одна из оставшихся строк не связана с новым Bitrix staging asset. В `docs/audits/sources/` нет скачанных raster-файлов; pinned PDF/HTML подтверждают identity и технические сведения, но сами по себе не документируют право извлечь и переиспользовать встроенные изображения.

Поэтому machine-vision/OCR очередь пуста: повторно просмотренные ранее assets исключены, а новых raster candidates нет.

## Артефакты

- `docs/audits/generated/rb-wave241b-media-acquisition-hold-ledger.csv` - полный ledger из 745 строк.
- `docs/audits/generated/rb-wave241b-media-acquisition-hold-ledger.summary.json` - счётчики, no-repeat union и safety state.
- `scripts/build-rb-wave241b-media-hold-ledger.py` - воспроизводимый builder с cardinality и drift gates.

## Safety

Сеть и БД не использовались. Apply не выполнялся. Backend-файлы и публикационные/коммерческие поля не изменялись.
