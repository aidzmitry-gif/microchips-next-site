# Срез реестра legacy URL по первому пакету (50 позиций)

Дата: 2026-07-26. Режим: read-only. Ни один товар не опубликован, ни одна
запись реестра не изменена — файлы `docs/audits/generated/*.csv` не
редактировались, только читались. Отчёт готовит решение владельца по
канонику/301, но сам решения не принимает: `final_url`/`new_url` в
реестре остаются пустыми, `decision` в реестре не менялся.

## Область и метод

Проверяется пересечение **первого пакета проверки идентичности (50 позиций,
`docs/imports/rb-first-50-fill-from-1c.csv`)** с реестром legacy URL:

- `docs/audits/generated/legacy-url-inventory.csv` (22 796 строк) — ранний
  снимок, поле `decision` = `unreviewed`/`status` = `pending`.
- `docs/audits/generated/legacy-url-decision-registry.csv` (28 267 строк) —
  обогащённый реестр, два вида строк (`registry_kind`): `sitemap_url`
  (22 796) и `legacy_redirect_rule` (5 471).
- `docs/audits/generated/legacy-redirect-source.csv` (5 471 строка) —
  сырые директивы `.htaccess` (`Redirect`/regex-правила), источник для
  `legacy_redirect_rule`.

Сопоставление велось программно (Python, `csv.DictReader`, полное
построчное сравнение `old_url`/`normalized_path` с полем «Ссылка на
сайте» пула 50), а не выборочно вручную — чтобы исключить пропуски.

## 1. Перепроверка счётчиков (собственный прогон)

| Проверка | Результат |
| --- | --- |
| Уникальных ID в пуле 50 | 50 (дублей нет) |
| Найдено 1:1 в `legacy-url-inventory.csv` | **50 / 50** |
| Найдено 1:1 в `legacy-url-decision-registry.csv` (`sitemap_url`) | **50 / 50** |
| `decision` в inventory для всех 50 | `unreviewed` (50/50), `new_url` пуст (50/50) |
| `decision` в registry для всех 50 (`sitemap_url`) | `fix` (50/50) |
| `review_status` в registry для всех 50 | `needs_review` (50/50) |
| `reason_code` в registry для всех 50 | `catalog_product_identity_requires_mapping` (50/50) |
| `final_url` в registry для всех 50 | пуст (50/50) — safeguard подтверждён |
| Строк `sitemap_url` с `redirect_rule_count != 0` среди 50 | **0** (у всех 50 sitemap-строк `redirect_rule_count = 0`) |
| Дополнительные строки `legacy_redirect_rule` с `old_url` = agm-путь одного из 6 ID | **6 / 6 найдены**, все с `redirect_rule_count = 1`, `decision = redirect`, `final_url` пуст |
| Итого строк реестра, относящихся к пакету 50 | 50 (sitemap_url) + 6 (legacy_redirect_rule) = **56** |

Установленные предыдущим агентом факты **подтверждены без расхождений**:
44 из 50 — ровно одна строка `sitemap_url` с decision/review_status/
reason_code как выше и без сопутствующего redirect-правила; 6 из 50
(все `gelevye`, все APC) — дополнительно имеют строку `legacy_redirect_rule`
с этой же парой ID, ведущую с AGM-пути на GEL-путь.

Важный нюанс, обнаруженный при перепроверке: 301-правило в реестре
привязано к **agm-варианту URL** (`old_url =
/catalog/akkumulyatory/dlya_ibp/agm/<id>/`), а не к gelevye-варианту,
который стоит в ссылке пула 50 и в sitemap. Поэтому у самой строки
`sitemap_url` (gelevye-путь) `redirect_rule_count = 0` — правило видно
только если отдельно искать `legacy_redirect_rule` по agm-пути того же
ID. Это не противоречит установленным фактам, но объясняет, почему
поверхностный поиск по `redirect_rule_count` в самой строке пакета его
не покажет.

## 2. Состав пакета (для навигации ревьюера)

42 позиции — категория `agm`, 8 — `gelevye`. Бренды: APC (41), Alarm
Force (6), B.B. Battery (2), MNB (1) — совпадает с
`2026-07-25-rb-first-50-product-audit.md`.

| Bitrix ID | Категория (URL) | Бренд-кандидат | MPN-кандидат | Есть 301 AGM→GEL? |
| ---: | --- | --- | --- | :---: |
| 1526 | agm | B.B. Battery | BC 17-12 | |
| 1645 | agm | B.B. Battery | BC 7-12 | |
| 2719 | agm | Alarm Force | FB 1.2-12 | |
| 2776 | agm | Alarm Force | FB 12-12 | |
| 2848 | agm | Alarm Force | FB 18-12 | |
| 2999 | agm | Alarm Force | FB 4.5-12 | |
| 3026 | agm | Alarm Force | FB 40-12 | |
| 3168 | agm | Alarm Force | FB 7.2-12 | |
| 3219 | agm | MNB | MM 75-12 | |
| 20088 | agm | APC | RBC7 | |
| 20090 | agm | APC | RBC43 | |
| 20091 | agm | APC | RBC4 | |
| 20092 | agm | APC | RBC2 | |
| 20093 | agm | APC | RBC143 | |
| 20094 | agm | APC | RBC110 | |
| 20095 | agm | APC | RBC6 | |
| 20096 | agm | APC | RBC55 | |
| 20097 | agm | APC | RBC48 | |
| 20098 | agm | APC | RBC34 | |
| 20099 | agm | APC | RBC22 | |
| 20100 | agm | APC | RBC17 | |
| 20101 | agm | APC | RBC140 | |
| 20102 | agm | APC | RBC124 | |
| 20103 | agm | APC | RBC123 | |
| 20104 | agm | APC | RBC106 | |
| 20105 | agm | APC | RBC105 | |
| 23785 | gelevye | APC | APCRBC133 | нет |
| 23786 | gelevye | APC | APCRBC132 | нет |
| 23794 | agm | APC | SYBT5 | |
| 23795 | agm | APC | RBC59 | |
| 23796 | agm | APC | RBC33 | |
| 23797 | agm | APC | RBC32 | |
| 23798 | agm | APC | RBC27 | |
| 23799 | agm | APC | RBC23 | |
| 23800 | agm | APC | RBC12 | |
| 23803 | agm | APC | APCRBC152 | |
| 23804 | agm | APC | RBC116 | |
| 23806 | agm | APC | RBC148 | |
| 23807 | agm | APC | RBC142 | |
| 23811 | agm | APC | RBC31 | |
| **23816** | **gelevye** | APC | RBC151 | **да** |
| **23817** | **gelevye** | APC | RBC150 | **да** |
| **23818** | **gelevye** | APC | APCRBC141 | **да** |
| **23820** | **gelevye** | APC | APCRBC136 | **да** |
| **23821** | **gelevye** | APC | APCRBC135 | **да** |
| **23824** | **gelevye** | APC | RBC8 | **да** |
| 23841 | agm | APC | RBC5 | |
| 23842 | agm | APC | RBC25 | |
| 23843 | agm | APC | RBC18 | |
| 23844 | agm | APC | RBC109 | |

Для всех 50 (без исключений) в реестре: `decision = fix`,
`review_status = needs_review`,
`reason_code = catalog_product_identity_requires_mapping`, `final_url`
пуст. Это означает: реестр **не** содержит готового канонического URL
ни для одной из 50 позиций — только фиксацию, что связка legacy-ID ↔
новый канон требует ручного маппинга.

## 3. Отдельный блок: 6 случаев AGM → GEL (эвидентность, не решение)

Для ID **23816, 23817, 23818, 23820, 23821, 23824** (все — бренд APC,
все — в разделе `gelevye` по данным sitemap/пула 50) в `.htaccess`
старого сайта найдено буквальное правило `Redirect` (не regex,
поэлементно, по одному на ID):

| ID | Правило (`legacy-redirect-source.csv`) |
| ---: | --- |
| 23816 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23816/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23816/` |
| 23817 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23817/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23817/` |
| 23818 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23818/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23818/` |
| 23820 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23820/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23820/` |
| 23821 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23821/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23821/` |
| 23824 | `Redirect /catalog/akkumulyatory/dlya_ibp/agm/23824/` → `https://microchips.by/catalog/akkumulyatory/dlya_ibp/gelevye/23824/` |

В обогащённом реестре (`legacy-url-decision-registry.csv`) для каждого
из 6 ID есть отдельная строка `registry_kind = legacy_redirect_rule` с
`old_url` = agm-путь, `legacy_target_raw` = gelevye-путь,
`decision = redirect`, `redirect_rule_count = 1`, `final_url` пуст
(генератор намеренно не проставляет цель — safeguard `reason`:
«The legacy redirect rule is source evidence only. Its target is not
adopted as a final URL»).

**Что это означает и чем не является:**

- Это факт: старый сайт (Bitrix) сам уже когда-то перенёс эти 6
  товаров из раздела AGM в раздел GEL и оставил 301 с прежнего
  AGM-адреса. Sitemap старого сайта сегодня отдаёт эти 6 ID только под
  `/gelevye/<id>/` — `/agm/<id>/` для них в sitemap не встречается.
- Это **не** утверждённое решение по канону/301 для нового сайта.
  Реестр специально хранит `legacy_target_raw` отдельно от `final_url`
  и не «повышает» одно в другое автоматически — так же, как и для
  остальных 5 465 правил `.htaccess`, не входящих в пакет 50.
- Ревьюеру: это сильная эвидентность в пользу того, что для этих 6 ID
  канон на новом сайте логично держать под `.../gelevye/<id>/`, а
  `.../agm/<id>/` — как редиректящий путь (если вообще воспроизводить
  адрес). Но решение (`keep`/`fix`/`redirect`/`remove` и конкретный
  `final_url`) остаётся за владельцем — этот отчёт его не проставляет
  и не проставит.
- Два оставшихся `gelevye`-ID пакета (**23785, 23786**) такого
  собственного 301-правила в `.htaccess` **не имеют** — они просто
  всегда числились под `gelevye`, без миграции. Отчёт не приравнивает
  их к 6 случаям с эвидентностью.

## 4. Риск дублей на одном и том же пути (для явного внимания владельца)

Путь-шаблон `/catalog/akkumulyatory/dlya_ibp/{agm|gelevye}/<id>/` —
**ровно тот же URL-шаблон**, который сегодня отдаёт живой Bitrix
(подтверждено: это и есть `old_url`/`normalized_path` в
`legacy-url-inventory.csv`/`legacy-url-decision-registry.csv`, взятые
из sitemap живого сайта). Из этого два конкретных риска:

1. **Общий риск дублей.** Если карточки нового сайта опубликовать по
   идентичному шаблону пути (тот же `/catalog/.../<технология>/<id>/`)
   до утверждения единственного канона и правил 301 со старого сайта,
   на какое-то время в интернете одновременно существуют две системы,
   отвечающие на один и тот же путь двумя разными сущностями (старый
   Bitrix и новый сайт) — классический риск дублирующего контента и
   конкуренции URL за один и тот же запрос, вплоть до путаницы для
   поисковика при сведении сигналов. Это ровно то, что фиксирует
   `reason_code = catalog_product_identity_requires_mapping` и почему
   `decision = fix` для всех 50, а не `keep`.
2. **Конфликт конкретно для 6 gelevye-ID.** Если бы кто-то опубликовал
   карточку одного из 6 ID (23816/23817/23818/23820/23821/23824) под
   `/catalog/akkumulyatory/dlya_ibp/agm/<id>/` (то есть под старым,
   уже отменённым путём) — это прямо конфликтует с уже действующим на
   старом сайте 301 `agm/<id>/ → gelevye/<id>/`: старый сайт уже говорит
   поисковику и пользователю «этого пути под AGM больше нет, товар
   переехал в GEL», а публикация новой карточки именно под AGM-адресом
   создала бы для того же ID второй, противоречащий сигнал.

Отчёт не делает вывод «поэтому canonical = gelevye для всех 6» —
это вывод, который должен зафиксировать владелец; здесь описан только
риск и его источник.

## 5. Что НЕ сделано (сознательно, это гейт владельца)

- `final_url` не проставлен ни для одной из 50 позиций — ни в этом
  отчёте, ни в `docs/audits/generated/*.csv` (файлы не менялись).
- Решения `keep`/`fix`/`redirect`/`remove` не приняты и не изменены —
  значения `decision` в реестре остаются такими, какими их вывел
  генератор (`unreviewed` в inventory, `fix`/`redirect` в decision
  registry как классификация «требует решения», а не финальный вердикт).
- `docs/audits/generated/` не редактировался вручную — только читался
  штатным Python-скриптом на чтение.

## 6. Ограничения данных

- Все три источника реестра — снимок бэкапа Bitrix от **2026-06-23**
  (см. `docs/audits/2026-07-14-b2b-catalog-slice.md` и другие аудиты
  того же извлечения). Датировка `.htaccess`-правил внутри бэкапа не
  проверялась отдельно от даты самого бэкапа.
- Живой краул (HTTP-запрос) этих 50 путей на текущем microchips.by
  **не выполнялся** в рамках этого среза — ни для проверки, что
  AGM-путь всех 6 ID сегодня физически отдаёт 301, ни для проверки,
  что sitemap не устарел. Если владелец хочет подтверждение «живым»
  ответом сервера, это отдельный шаг (осторожно: даже безобидный GET
  на прод — операция, которую стоит явно одобрить, а не проводить
  тихо).
- Отчёт не проверял, отдаёт ли живой Bitrix сегодня *иные* 301/404 по
  этим 50 путям, кроме зафиксированных в `.htaccess`-снимке 2026-06-23.

## Источники (воспроизводимость)

| Файл | Роль |
| --- | --- |
| `docs/imports/rb-first-50-fill-from-1c.csv` | Пул 50 ID + ссылки + бренд/MPN-кандидаты |
| `docs/audits/generated/legacy-url-inventory.csv` | Ранний снимок реестра URL (не редактировался) |
| `docs/audits/generated/legacy-url-decision-registry.csv` | Обогащённый реестр `sitemap_url` + `legacy_redirect_rule` (не редактировался) |
| `docs/audits/generated/legacy-redirect-source.csv` | Сырые директивы `.htaccess` (не редактировался) |

Все счётчики в разделе 1 перепроверены прямым построчным сопоставлением
(Python, `csv.DictReader`) в рамках этой сессии, а не переписаны со
слов предыдущего агента.
