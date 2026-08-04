#!/usr/bin/env python3
"""Find strict near-duplicate candidates inside a classified lighting slice.

This is a review report, not a merge or deletion tool.  It removes only
non-identity decoration commonly appended by the 1C export (country/origin and
barcode wording) and retains every model, voltage, power and base token.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def key(name: str) -> str:
    value = name.casefold()
    value = re.sub(
        r"(?:[,;.]?\s*)?(?:страна\s+(?:происхождения|ввоза)|производство|пр-во|изготовитель)\s*[:.-]?\s*[^,.;]*",
        " ",
        value,
    )
    value = re.sub(r"(?:ш/?к|ean)\s*\d{8,14}", " ", value)
    value = re.sub(r"\b(?:россия|рф|китай|кнр)\b", " ", value)
    return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    names = {
        row["product_external_id"].strip(): row["name"].strip()
        for row in csv.DictReader(args.source.open(encoding="utf-8-sig", newline=""))
        if row.get("product_external_id", "").strip() and row.get("name", "").strip()
    }
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in csv.DictReader(args.assignments.open(encoding="utf-8-sig", newline="")):
        external_id = row.get("product_external_id", "").strip()
        name = names.get(external_id, "")
        normalized = key(name)
        if len(normalized) >= 8 and any(char.isdigit() for char in normalized):
            groups[normalized].append({
                "product_external_id": external_id,
                "name": name,
                "category_external_id": row.get("category_external_id", "").strip(),
            })

    rows: list[dict[str, str]] = []
    for normalized, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        members.sort(key=lambda item: item["product_external_id"])
        survivor = members[0]
        for candidate in members[1:]:
            rows.append({
                "duplicate_key": normalized,
                "survivor_external_id": survivor["product_external_id"],
                "survivor_name": survivor["name"],
                "duplicate_external_id": candidate["product_external_id"],
                "duplicate_name": candidate["name"],
                "category_external_id": candidate["category_external_id"],
                "confidence": "strict_model_after_origin_and_barcode_cleanup",
                "action": "review_identity_before_excluding_or_merging",
            })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "duplicate_key", "survivor_external_id", "survivor_name",
        "duplicate_external_id", "duplicate_name", "category_external_id",
        "confidence", "action",
    ]
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"strict_lighting_duplicate_pairs={len(rows)}")


if __name__ == "__main__":
    main()
