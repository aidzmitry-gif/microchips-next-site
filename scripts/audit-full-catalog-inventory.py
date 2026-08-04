#!/usr/bin/env python3
"""Audit the complete Bitrix ↔ 1C catalog before any publication.

This script is deliberately read-only: it never creates Laravel products.  It
turns the full Bitrix export and the current 1C nomenclature into auditable
facts: coverage, deterministic duplicate candidates and a research queue for
thin/poorly identified product pages.  A candidate is never an automatic merge.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

GENERIC = {
    "аккумулятор", "аккумуляторная", "батарея", "батарейка", "источник",
    "питания", "бесперебойного", "для", "и", "с", "в", "на", "the",
}
HEADER = [
    "candidate_key", "candidate_type", "confidence", "bitrix_ids",
    "names", "section_paths", "one_c_codes", "reason", "action",
]
RESEARCH_HEADER = [
    "bitrix_id", "name", "section_path", "one_c_code", "match_method",
    "research_priority", "reason", "publication_rule",
]


def text(value: str | None) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def norm(value: str | None) -> str:
    raw = text(value).casefold()
    # Decimal separators are semantic: "1.2 Ah" must never collide with
    # "12 Ah" merely because punctuation was removed during normalization.
    raw = re.sub(r"(?<=\d)[.,](?=\d)", " decimal ", raw)
    return re.sub(r"[^0-9a-zа-я]+", "", raw)


def tokens(value: str | None) -> list[str]:
    return [
        item for item in re.findall(r"[0-9a-zа-я]+", text(value).casefold())
        if item not in GENERIC
    ]


def model_key(name: str) -> str:
    """Conservative model signature: only useful when it contains a digit."""
    parts = tokens(name)
    if not any(any(char.isdigit() for char in item) for item in parts):
        return ""
    return "-".join(parts)


def load_bitrix(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    needed = {"Bitrix ID", "Название (сайт)", "Раздел", "Активен", "1С-код", "match_method"}
    missing = needed.difference(rows[0] if rows else {})
    if missing:
        raise ValueError(f"Bitrix export has no required columns: {sorted(missing)}")
    return rows


def load_one_c(path: Path) -> tuple[list[dict[str, str]], int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    if not rows or len(rows[0]) < 7:
        raise ValueError("1C export is empty or has an unexpected schema")
    products: list[dict[str, str]] = []
    groups = 0
    for row in rows[1:]:
        if len(row) < 7:
            continue
        is_group = text(row[3]).casefold() in {"истина", "true", "1", "да"}
        if is_group:
            groups += 1
            continue
        products.append({"code": text(row[0]), "article": text(row[1]), "name": text(row[2]), "path": text(row[6])})
    return products, groups


def append_candidates(
    output: list[list[str]], groups: dict[str, list[dict[str, str]]], candidate_type: str, confidence: str,
) -> None:
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        output.append([
            key, candidate_type, confidence,
            "|".join(item["Bitrix ID"] for item in items),
            " | ".join(item["Название (сайт)"] for item in items),
            " | ".join(item["Раздел"] for item in items),
            "|".join(item["1С-код"] for item in items if text(item["1С-код"])),
            "Совпадение формируется только по стабильному ключу; модель и источник должны быть перепроверены.",
            "Не сливать автоматически; сохранить один товар только после доказуемой идентичности.",
        ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bitrix", type=Path, required=True)
    parser.add_argument("--one-c", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bitrix = load_bitrix(args.bitrix)
    one_c, one_c_groups = load_one_c(args.one_c)
    args.out.mkdir(parents=True, exist_ok=True)

    active = [row for row in bitrix if text(row["Активен"]).upper() == "Y"]
    exact_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    exact_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in active:
        name = norm(row["Название (сайт)"])
        if name:
            exact_name[name].append(row)
        model = model_key(row["Название (сайт)"])
        if model:
            exact_model[model].append(row)

    candidates: list[list[str]] = []
    append_candidates(candidates, exact_name, "exact_normalized_name", "review_required")
    # Do not report a model key twice when it is exactly the same as its name key.
    append_candidates(candidates, {
        key: values for key, values in exact_model.items() if key not in exact_name or len(exact_name[key]) < 2
    }, "exact_model_signature", "review_required")

    one_c_codes = Counter(item["code"] for item in one_c if item["code"])
    mapped = [row for row in active if text(row["1С-код"])]
    match_methods = Counter(text(row["match_method"]) or "unknown" for row in active)
    research: list[list[str]] = []
    for row in active:
        title = text(row["Название (сайт)"])
        reasons: list[str] = []
        if not text(row["1С-код"]):
            reasons.append("нет доказуемой связи с 1С")
        if not model_key(title):
            reasons.append("в названии нет устойчивого кода модели")
        if len(tokens(title)) <= 2:
            reasons.append("название слишком короткое для самостоятельной идентификации")
        if reasons:
            research.append([
                row["Bitrix ID"], title, row["Раздел"], row["1С-код"], row["match_method"],
                "high" if len(reasons) >= 2 else "medium", "; ".join(reasons),
                "Не публиковать в индекс до первичного источника производителя, спецификации и изображения.",
            ])

    def write_csv(filename: str, header: list[str], rows: list[list[str]]) -> None:
        with (args.out / filename).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    write_csv("full-catalog-duplicate-candidates.csv", HEADER, candidates)
    write_csv("full-catalog-research-queue.csv", RESEARCH_HEADER, research)
    summary = {
        "source": {"bitrix_csv": str(args.bitrix), "one_c_csv": str(args.one_c)},
        "bitrix": {"all_products": len(bitrix), "active_products": len(active), "inactive_products": len(bitrix) - len(active)},
        "one_c": {"product_rows": len(one_c), "group_rows": one_c_groups, "duplicate_codes": sum(count > 1 for count in one_c_codes.values())},
        "mapping": {"active_bitrix_with_one_c_code": len(mapped), "active_bitrix_without_one_c_code": len(active) - len(mapped), "match_methods": dict(sorted(match_methods.items()))},
        "duplicate_candidates": {"groups": len(candidates), "rows_in_groups": sum(len(row[3].split("|")) for row in candidates)},
        "research_queue": {"products": len(research), "rule": "research queue is not a publication queue"},
        "safety": "No merge, publication, price, availability, manufacturer description or image is inferred by this audit.",
    }
    (args.out / "full-catalog-inventory-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
