# Wave246A — EnerSys pending B2B media scope

Scope строго равен 92 строкам `partition=enersys` из `rb-wave246-b2b-scope.csv`: Cyclon 15, DataSafe HX 17, PowerSafe V-FT 9, PowerSafe SBS 32, PowerSafe RH 19.

No-repeat scan показал, что identity и source-backed description уже выполнены для 92/92 строк в waves 179/183/193/209A/241. Поэтому новые identity/description manifests не создавались: stageable rows = 0. Все 92 строки действительно остаются pending только по media (`has_verified_published_image=false`).

Пять ранее зафиксированных manufacturer-primary family sources переиспользованы без повторной загрузки. Cyclon PDF SHA-256 `3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f`; страницы 11, 15, 17, 18 отрендерены и визуально проверены. Новый источник только один: официальный EnerSys Terms of Use, SHA-256 `20a2e07b12742f09758440aceeb11de72fdb0523dbdc377572a98bf1c168fc66`. Он разрешает лишь personal/non-commercial use и не даёт права коммерчески публиковать отдельные изображения без письменного разрешения.

Live read-only snapshot: 92/92 имеют ровно одного exact normalized EnerSys+MPN owner; exact 1C conflicts = 0; duplicate collapse actions = 0. Prefix-пары вроде `12V100F`/`12V100FC` и `SBS 30`/`SBS 300` не считаются дублями.

Итог: PASS 0, HOLD 92. Для девяти scope Cyclon rows уже существующие company-owned candidates ранее получили visual HOLD из-за нечитаемой/неполной маркировки; для остальных exact model media candidate отсутствует. Дополнительно официальный rights gate запрещает promotion manufacturer assets. Media manifests на импорт не создавались.

Laravel validation выполнена через временные (не import) subsets: identity dry-run для 15 Bitrix rows — PASS, 0 commercial/publication changes; description dry-run для всех 92 — 92 unchanged, none published; read-only manufacturer preview verifier для остальных 77 — PASS. Постоянные повторные identity/description manifests не создавались. Apply/commit/push не выполнялись.
