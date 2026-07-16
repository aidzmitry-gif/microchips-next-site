# Engineering Loop для проекта microchips-next-site

Переиспользуемый процесс для инжиниринг-цикла: Inspect → Change → Verify → Commit.

## Цикл работы

### 1. Inspect (осмотр)

Начало каждого цикла — состояние рабочего дерева.

```bash
git status --short
```

**Правила:**
- Не трогать WIP (Work In Progress) коллег на других ветках — работать только в своей `codex/*` или фиксе.
- Предпочитать стабильные поверхности для изменений:
  - Доки (`docs/*.md`, `README.md`)
  - Скрипты верификации (`scripts/verify-*.ps1`)
  - Конфигурация и тесты
- Избегать множественных изменений одновременно — один цикл = одно намерение.

### 2. Change (изменение)

Каждое изменение должно быть **аддитивным** и **сосредоточенным**.

**Требования:**
- **Одно намерение:** одна фича, один баг-фикс, одно уточнение документации. Если возникает второе — завершить текущий цикл, закоммитить, запустить новый.
- **Обновлять соседние доки:** если меняется процесс или скрипт, обновить ссылающуюся документацию (CLAUDE.md, процесс-доки в docs/).
- **Не трогать генерируемое:** папка `docs/audits/generated/` в `.gitignore` — скрипты пересчитывают её при каждом запуске. Редактировать только источники (Bitrix SQL, скрипты extraction).
- **Сохранять честность данных:** не выдумывать цену/наличие/SKU/сертификаты/юрлицо. Статус заказа — только «по запросу»/«требует подтверждения» до подтверждения источника.

### 3. Verify (проверка)

Выход из цикла ТОЛЬКО при зелёном автоматическом гейте.

**Типовые гейты проекта:**

| Что меняется | Гейт | Команда |
|---|---|---|
| Прототипы RB (`docs/prototypes/rb-b2b-*.html`) | verify-rb-prototype.ps1 | `.\scripts\verify-rb-prototype.ps1` |
| Extractor Bitrix (`scripts/extract-*.ps1`) | Dry-run гейт | `.\scripts\extract-bitrix-b2b-catalog-slice.ps1 -WhatIf` |
| Manifest RB (1569 строк) | Встроенная сверка счётчиков | `.\scripts\build-rb-import-manifest.ps1` (падает при расхождении 1569/1445/124) |
| Nomenclature audit (находки) | Адверсариальная проверка | Запустить `audit-rb-nomenclature.py`, прочитать findings CSV, проверить sample-строк вручную |

**Обязательно перед Commit:**
- Статические проверки должны пройти single-pass (не требуя переделок).
- Для данных: результаты audit/manifest перепроверить адверсариально — ложные срабатывания удалить (в этой сессии дважды находили и чинили собственные баги детекторов до того, как отчёт ушёл дальше).

### 4. Commit

Фиксация изменений в git.

**Правила:**
- **Только свои файлы:** `git add имя_файла` (перечислить файлы явно), НЕ `git add .` или `git add -A` (риск случайных переделок).
- **Сообщение:** коротко, формат `area: action` (например, `docs: update engineering-loop description`, `scripts: add rb-prototype self-test`).
- **Push:** только по явной просьбе пользователя. На Windows сообщение вида «LF will be replaced by CRLF» — норма.
- **Co-author:** если это сесссия Claude, добавить trailer в сообщение.

Пример:
```bash
git add docs/engineering-loops/ENGINEERING-LOOP.md
git commit -m "docs: add engineering-loop process document

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

## Работа с данными

Когда изменяются данные (прайс, номенклатура, вывод товаров), придерживаться цепочки:

```
Extract (SQL Bitrix) → Manifest (1569-row slice) → Audit (nomenclature findings)
```

**Если нужен свежий цикл:**
1. **Фикс в источнике:** исправить ошибку в базе Bitrix (если возможно) или в логике скрипта extraction.
2. **Свежая выгрузка:** перезапустить `extract-bitrix-b2b-catalog-slice.ps1` (очистит кэш).
3. **Перегон manifest:** `build-rb-import-manifest.ps1` пересчитает 1569 строк.
4. **Перегон audit:** `audit-rb-nomenclature.py` сгенерирует новый findings CSV и xlsx.

Счётчики фокуса (1569 = 1445 primary + 124 secondary) зафиксированы аудитом. Если генератор падает — расхождение, надо диагностировать.

## Техническое напоминание: PowerShell и BOM

Все `.ps1`-скрипты в проекте содержат кириллицу (комментарии, переменные, вывод). На Windows PowerShell 5.1 требуется:

**Кодировка: UTF-8 с BOM (Byte Order Mark)**

Без BOM парсер падает с ошибкой типа `Unexpected token`. Если скрипт редактировался в текстовом редакторе без BOM:

```powershell
# Признак проблемы: скрипт с кириллицей падает с "Unexpected token" на первой
# же кириллической строке. Лечение — перечитать без BOM и записать с BOM:
$content = [System.IO.File]::ReadAllText($p, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($p, $content, [System.Text.UTF8Encoding]::new($true))
```

Это НЕ дефект скрипта — это особенность Windows + PowerShell. Другие платформы (macOS, Linux) могут обойтись без BOM.

---

**Дата последнего обновления:** 2026-07-16  
**Ветка:** codex/harden-rb-b2b-boundaries
