# Wave 150 — массовые изображения из Bitrix для noindex-каталога

Дата: 2026-07-28

## Результат

- В legacy staging найдено `1 568` целостных растровых файлов.
- `1 464` файла относятся к опубликованным бесспорным namespaced Bitrix-карточкам.
- Все `1 464` изображения привязаны к товару по исходному Bitrix element ID, а не по названию.
- `104` файла для hold/исключённых/непубличных записей не опубликованы автоматически.

## Модель доверия

- Новый статус: `legacy_exact_preview`.
- Он подтверждает точную техническую связь `Bitrix element -> PREVIEW/DETAIL_PICTURE` и принадлежность резервной копии компании.
- Он не означает визуальную проверку модели и не увеличивает счётчик `storefrontReady`/SEO-complete.
- Существующие `88` вручную проверенных изображений сохраняют статус `verified`.

## Защита индексации

- У preview-изображений нет индексируемых товарных URL: `0`.
- Media endpoint отдаёт `X-Robots-Tag: noindex, noarchive`.
- Preview-файл отдаётся с `Cache-Control: private, no-store, max-age=0`.
- Next.js media proxy передаёт robots/cache headers backend без ослабления.

## Проверка

- PHP syntax: новый command и модель — без ошибок.
- Dry-run: `1 464` eligible, первый batch `500`, без мутаций indexability.
- Apply: три идемпотентных пакета, итог `1 464`.
- Next.js production build: успешен, TypeScript успешен.
- Сквозная карточка `/catalog/industrial-batteries/batteries-ups/legacy-bitrix-845`: HTTP 200, содержит `/api/media/{id}`.
- Media proxy: HTTP 200, `image/png`, `noindex, noarchive`.

Следующий цикл: убрать полный пересчёт фасетов на каждом запросе каталога и подтвердить скорость на 16k+ карточках.
