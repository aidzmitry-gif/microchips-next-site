#!/usr/bin/env python3
"""Extract explicitly written technical facets from source product names.

Values remain evidence candidates.  They may power internal review and filter
coverage reports, but cannot become a published specification without a
manufacturer document or another primary source.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

TECHNOLOGIES = {
    "lifepo4": "LiFePO4", "li-ion": "Li-ion", "li ion": "Li-ion", "li-pol": "Li-pol",
    "li pol": "Li-pol", "nimh": "NiMH", "ni-mh": "NiMH", "nicd": "NiCd", "ni-cd": "NiCd",
    "agm": "AGM", "gel": "GEL", "vrla": "VRLA", "opzs": "OPzS", "opzv": "OPzV",
}
VOLTAGE = re.compile(r"(?<![a-zа-я0-9])([0-9]+(?:[.,][0-9]+)?)\s*(?:v|в)(?![a-zа-я0-9])", re.I)
CAPACITY = re.compile(r"(?<![a-zа-я0-9])([0-9]+(?:[.,][0-9]+)?)\s*(mah|ah|ма\s*ч|а\s*ч)(?![a-zа-я0-9])", re.I)


def extract(name: str) -> tuple[str, str, str]:
    lowered = name.casefold()
    voltage = VOLTAGE.search(lowered)
    capacity = CAPACITY.search(lowered)
    technologies = sorted({label for needle, label in TECHNOLOGIES.items() if needle in lowered})
    return (
        voltage.group(1).replace(",", ".") if voltage else "",
        (capacity.group(1).replace(",", ".") + " " + capacity.group(2).replace(" ", "")) if capacity else "",
        "|".join(technologies),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with args.registry.open(encoding="utf-8-sig", newline="") as handle:
        products = [row for row in csv.DictReader(handle) if row["is_active"] == "true"]

    rows: list[list[str]] = []
    coverage = Counter()
    technologies = Counter()
    for product in products:
        voltage, capacity, technology = extract(product["name"])
        if voltage:
            coverage["voltage"] += 1
        if capacity:
            coverage["capacity"] += 1
        if technology:
            coverage["technology"] += 1
            technologies.update(technology.split("|"))
        rows.append([
            product["bitrix_id"], product["name"], product["legacy_section_path"],
            voltage, capacity, technology,
            "name_evidence_only",
            "Do not publish as a specification until a primary manufacturer source confirms it.",
        ])

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "full-catalog-facet-evidence.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["bitrix_id", "name", "legacy_section_path", "voltage_candidate", "capacity_candidate", "technology_candidate", "evidence_status", "publication_rule"])
        writer.writerows(rows)
    summary = {
        "active_products": len(products),
        "coverage": {key: {"products": coverage[key], "percent": round(100 * coverage[key] / len(products), 2)} for key in ("voltage", "capacity", "technology")},
        "technology_candidates": dict(technologies.most_common()),
        "invariant": "A missing value means unknown, not zero. Extracted values are not published specifications.",
    }
    (args.out / "full-catalog-facet-evidence-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
