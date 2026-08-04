# Wave 231 — исправление MPN и карантин неверных изображений каталога РБ

Дата: 2026-07-29  
Профиль: `microchips-by`

## Результат

- Машинно-визуальная перепроверка семи спорных legacy-изображений разделила их на пять изображений другого товара и два случая усечённого MPN.
- Пять неверных изображений безопасно переведены в `needs_review` и сняты с публикации: `bitrix:2808`, `bitrix:2909`, `bitrix:3056`, `bitrix:3099`, `bitrix:3219`.
- Два MPN исправлены только после совпадения официального PDF Exide и видимой маркировки собственного изображения:
  - `bitrix:2831`: `S 12/17` → `S 12/17 G5`;
  - `bitrix:3117`: `S 12/6` → `S 12/6.6 S`.
- После исправления идентичности изображения `607` и `834` повторно прошли exact-MPN gate и переведены в `verified`.
- Два legacy-описания заменены на `manufacturer_primary` / `official_manufacturer_catalogue` описания с ограниченной областью идентичности `model_core`.
- Цена, наличие, статус региональной публикации и другие коммерческие поля не изменялись. У обеих завершённых карточек сохранено честное состояние `availability=on_request`, `price=NULL`.

## Усиление fail-closed защиты

- `hold_truncated_identity_preview` теперь принимает только строгий prefix-compatible MPN, полный вариант которого присутствует в названии товара.
- Манифест карантина обязан закреплять локальный файл визуального аудита, его SHA-256 и автора проверки.
- Исправление MPN обязано фактически перечитать локальный официальный snapshot и извлечение, проверить их SHA-256 и присутствие доказательной строки.
- Перед записью Product, SiteProduct и ProductMedia повторно блокируются и сверяются внутри транзакции.
- Ошибка отправки события revalidation больше не может пометить уже зафиксированное изменение как неуспешную транзакцию.

## Метрики

| Метрика | До | После | Изменение |
|---|---:|---:|---:|
| Content-complete | 337 | 339 | +2 |
| Strict content ready | 158 | 160 | +2 |
| Очередь обогащения до 10% | 1305 | 1303 | -2 |
| Content-complete от базы 16 415 | 2,053% | 2,065% | +0,012 п.п. |

Полное распределение после Wave231: `legacy_content_preview=14725`, `legacy_preview_only=103`, `legacy_text_only=923`, `source_backed_partial=898`, `strict_content_ready=160`, `thin_unidentified=7`.

Общая подтверждённая готовность проекта остаётся **60%**: этот цикл улучшил качество каталога, но не закрыл остальные гейты запуска и 14-дневное наблюдение.

## Аудиторские записи

- ImportRun `994`: quarantine dry-run, 7/7.
- ImportRun `995`: MPN correction dry-run, 2/2.
- ImportRun `996`: quarantine apply, 5 quarantined + 2 holds, без product/site/commercial changes.
- ImportRun `997`: MPN correction apply, 2 исправления, без commercial/publication changes.
- ImportRun `998–999`: source-backed stage dry-run/apply, 2 refreshed.
- ImportRun `1000–1001`: source-backed description dry-run/apply, 2 applied, без commercial/publication changes.

## Верификация

- Laravel: 6 тестов, 57 assertions — успешно.
- Python builders: 7 тестов — успешно.
- Production dry-run: quarantine 7/7; MPN correction 2/2; media promotion 2/2; description stage/apply 2/2.
- Post-apply DB audit: пять неверных media unpublished; два исправленных MPN, два verified media и два applied manufacturer-primary drafts.
- SEO audit: 16 853 URL, 97 редиректов, 0 блокирующих проблем.
- `scripts/verify-rb-prototype.ps1`: все четыре HTML-прототипа прошли.

Подробный machine-readable receipt: `docs/audits/generated/wave231-identity-media-repair-receipt.json`.

