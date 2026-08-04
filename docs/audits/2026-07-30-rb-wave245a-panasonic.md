# Wave245A — Panasonic LC-XC1222P / LC-XC1228P

Проверены только новые строки очереди `bitrix:1569` и `bitrix:1580`.

- prior scan: 375 структурированных файлов, 2 654 URL и 1 145 SHA-256; пересечений у новых datasheet URL/SHA нет;
- live ownership: для каждой модели найден ровно один продукт — соответствующий Bitrix draft; exact 1C owner отсутствует, поэтому collapse не требуется и не создавался;
- identity/description: PASS по новым индивидуальным datasheet Panasonic (12 В; 22/28 А·ч; габариты, масса и M5);
- media: official exact datasheet photos извлечены и визуально сверены, но HOLD — явная лицензия на перераспространение не найдена;
- никаких apply/DB mutations/commit/push.

PDF визуально отрендерены: модель, фото, размерный чертёж и таблица характеристик согласованы на первых страницах обоих datasheet. Утверждение AGM в legacy title в новые description facts не переносится: exact datasheet его на проверенных страницах не подтверждает.

Верификация: Python contract test — `1 passed`; реальный Laravel identity dry-run — 2 records, 0 commercial/publication changes; description dry-run — 2 unchanged, none published. Флаг `--apply` не использовался.
