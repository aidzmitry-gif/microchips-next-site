#!/usr/bin/env python3
"""Find high-confidence duplicate 1C candidates without merging products.

The comparison removes only boilerplate country/origin tails and punctuation.
Each group records a deterministic survivor proposal but remains an audit
candidate until the site-draft exclusion gate validates it.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def key(name: str) -> str:
    value = name.casefold()
    value = re.sub(r"(?:[,;.]?\s*)?(?:страна\s+(?:происхождения|ввоза|изготовитель)[^,.;]*|производство\s*[:.-]?\s*[^,.;]*|произ-во\s*[:.-]?\s*[^,.;]*)", "", value)
    return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--exclude", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exclusion-delta", type=Path, required=True)
    args = parser.parse_args()
    excluded = {r["product_external_id"] for r in csv.DictReader(args.exclude.open(encoding="utf-8-sig", newline=""))}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            if row.get("ЭтоГруппа", "").strip().casefold() not in {"ложь", "false", "0", "no", "n"}:
                continue
            external_id, name = row.get("Код", "").strip(), row.get("Наименование", "").strip()
            if not external_id or not name or external_id in excluded:
                continue
            normalized = key(name)
            # A strict canonical duplicate should still look like a product/model,
            # not a short generic service wording.
            if len(normalized) >= 8 and any(char.isdigit() for char in normalized):
                groups[normalized].append({"product_external_id": external_id, "name": name})
    rows, delta = [], []
    for normalized, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        items.sort(key=lambda item: item["product_external_id"])
        survivor = items[0]
        for duplicate in items[1:]:
            rows.append({"duplicate_key": normalized, "survivor_external_id": survivor["product_external_id"], "survivor_name": survivor["name"], "duplicate_external_id": duplicate["product_external_id"], "duplicate_name": duplicate["name"], "confidence": "strict_normalized_name"})
            delta.append({"product_external_id": duplicate["product_external_id"], "reason": "strict_duplicate_candidate", "survivor_external_id": survivor["product_external_id"]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["duplicate_key", "survivor_external_id", "survivor_name", "duplicate_external_id", "duplicate_name", "confidence"])
        writer.writeheader(); writer.writerows(rows)
    with args.exclusion_delta.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "reason", "survivor_external_id"])
        writer.writeheader(); writer.writerows(delta)
    print(f"strict_duplicate_pairs: {len(rows)}")


if __name__ == "__main__":
    main()
