#!/usr/bin/env python3
"""Rank unresolved technical catalogue rows for source-first enrichment.

This intentionally creates a research queue, not descriptions. A high score
means the name likely contains a model/technical signal and is worth checking
against a manufacturer or an authorized technical document first.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def unicode_regex(pattern: str) -> re.Pattern[str]:
    """Decode unicode tokens in raw regexes without changing other escapes."""
    return re.compile(
        _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), pattern),
        re.I,
    )


# Current 1C exports are UTF-8. These patterns rank the current source rather
# than inheriting old mojibake compatibility expressions below.
TECH_UTF8 = unicode_regex(
    r"\u0430\u043a\u043a\u0443\u043c|\u0431\u0430\u0442\u0430\u0440\u0435|\u044d\u043b\u0435\u043c\u0435\u043d\u0442\s+\u043f\u0438\u0442\u0430\u043d|"
    r"\u043b\u0438\u0442\u0438\u0435\u0432|li[- ]?ion|ni[- ]?mh|lifepo|"
    r"\u043c\u0438\u043a\u0440\u043e\u0441\u0445\u0435\u043c|\u043e\u043f\u0442\u0440\u043e\u043d|\u043c\u043e\u0434\u0443\u043b\u044c|\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440|"
    r"\u0434\u0430\u0442\u0447\u0438\u043a|\u0440\u0430\u0437\u044a[\u0435\u0451]\u043c|\u0434\u0438\u0441\u043f\u043b\u0435\u0439|"
    r"\u0442\u0440\u0430\u043d\u0441\u0444\u043e\u0440\u043c\u0430\u0442\u043e\u0440|\u0434\u0440\u043e\u0441\u0441\u0435\u043b\u044c|\u0432\u0435\u043d\u0442\u0438\u043b\u044f\u0442\u043e\u0440|"
    r"\u0440\u0435\u043b\u0435|\u0438\u043d\u0432\u0435\u0440\u0442\u043e\u0440|\u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c|"
    r"\u043c\u0443\u043b\u044c\u0442\u0438\u043c\u0435\u0442\u0440|\u0442\u0435\u0441\u0442\u0435\u0440|\u0437\u0430\u0440\u044f\u0434\u043d|"
    r"\u043f\u0430\u044f\u043b\u044c\u043d|\u0441\u0432\u0435\u0442\u0438\u043b\u044c\u043d\u0438\u043a|\u043b\u0430\u043c\u043f",
)
MODEL_UTF8 = re.compile(r"(?=.*\d)(?=.*[A-Za-zА-Яа-я])[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9./_-]{3,}")
BRANDS_UTF8 = re.compile(r"saft|energizer|panasonic|philips|delta|ventura|fiamm|varta|renata|camelion|robiton|tekcell|fanso|samsung|lg|sony|kingbright|omron|tp-link|trimble|uni-t|mastech|sunshine|dji|betafpv|iflight", re.I)
VISIBLE_SPEC_UTF8 = re.compile(r"\b(?:\d+(?:[.,]\d+)?\s*(?:v|в|mah|мач|ah|ач|w|вт|f|ф))\b", re.I)


TECH = re.compile(r"аккум|батаре|элемент питан|литиев|li[- ]?ion|ni[- ]?mh|lifepo|микросхем|оптрон|модул|контроллер|датчик|разъ[её]м|дисплей|трансформатор|резонатор|дроссел|вентилятор|реле|инвертор|преобразовател", re.I)
MODEL = re.compile(r"(?=.*\d)(?=.*[A-Za-zА-Яа-я])[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9./_-]{3,}")
BRANDS = re.compile(r"saft|energizer|panasonic|philips|delta|ventura|fiamm|varta|renata|camelion|robiton|tekcell|fanso|samsung|lg|sony|kingbright|omron|tp-link|trimble", re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.input.open(encoding="utf-8-sig", newline="")))
    ranked = []
    for row in rows:
        external_id = (row.get("product_external_id") or row.get("external_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not external_id or not name:
            continue
        score = 0
        reasons = []
        if TECH_UTF8.search(name):
            score += 4; reasons.append("technical_type")
        if MODEL_UTF8.search(name):
            score += 3; reasons.append("model_like_token")
        if BRANDS_UTF8.search(name):
            score += 3; reasons.append("known_brand_token")
        if re.search(r"\b(?:\d+(?:[.,]\d+)?\s*(?:v|в|mah|мач|ah|ач|w|вт|f|ф))\b", name, re.I):
            score += 2; reasons.append("visible_spec")
        if score >= 4:
            ranked.append({
                "product_external_id": external_id,
                "name": name,
                "priority_score": str(score),
                "priority_reasons": "|".join(reasons),
                "row_number": row.get("row_number", ""),
                "rule": row.get("rule", ""),
                "scope_reason": row.get("scope_reason", ""),
            })
    ranked.sort(key=lambda row: (-int(row["priority_score"]), row["product_external_id"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["product_external_id", "name", "priority_score", "priority_reasons", "row_number", "rule", "scope_reason"]
        # The research input may contain useful source columns (manufacturer,
        # MPN, existing short description).  The output is deliberately a
        # compact queue, so ignore those extra keys rather than failing after
        # a long export has already completed.
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(ranked)
    print(f"priority_research_rows: {len(ranked)}")


if __name__ == "__main__":
    main()
