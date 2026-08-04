#!/usr/bin/env python3
"""Freeze 276 genuinely pending B2B rows into three manufacturer-family partitions."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave245.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.summary.json"

PARTITIONS = {
    "enersys": {"manufacturers": {"EnerSys"}, "limit": 92},
    "csb": {"manufacturers": {"CSB"}, "limit": 92},
    "delta_leoch": {"manufacturers": {"Delta", "LEOCH"}, "limit": 92},
}
B2B_CATEGORY_PREFIXES = (
    "seo:batteries-",
    "seo:power-",
    "seo:ups-",
    "seo:chargers",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with QUEUE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    eligible = [
        row for row in rows
        if row["research_status"] == "pending_official_source_research"
        and row["category_external_id"].startswith(B2B_CATEGORY_PREFIXES)
    ]
    selected: list[dict[str, str]] = []
    for partition, config in PARTITIONS.items():
        candidates = [
            row for row in eligible
            if row["manufacturer"] in config["manufacturers"]
            and row["mpn"].strip()
        ]
        candidates.sort(key=lambda row: (int(row["priority"]), row["product_external_id"]))
        chosen = candidates[: config["limit"]]
        if len(chosen) != config["limit"]:
            raise RuntimeError(f"Partition {partition} has only {len(chosen)} rows")
        for row in chosen:
            identity = row["mpn"].strip()
            if not identity:
                raise RuntimeError(f"{row['product_external_id']} lacks a pinned identity")
            selected.append({
                "partition": partition,
                "scope_order": str(len(selected) + 1),
                **row,
            })
    keys = [row["product_external_id"] for row in selected]
    if len(keys) != 276 or len(set(keys)) != len(keys):
        raise RuntimeError("Wave246 scope must contain 276 unique rows")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    summary = {
        "schema_version": 1,
        "wave": "wave246_b2b_family_research",
        "source_queue": str(QUEUE.relative_to(ROOT)).replace("\\", "/"),
        "source_queue_sha256": sha256(QUEUE),
        "rows": len(selected),
        "partitions": dict(sorted(Counter(row["partition"] for row in selected).items())),
        "manufacturers": dict(sorted(Counter(row["manufacturer"] for row in selected).items())),
        "all_pending_before_freeze": all(row["research_status"] == "pending_official_source_research" for row in selected),
        "all_b2b": all(row["category_external_id"].startswith(B2B_CATEGORY_PREFIXES) for row in selected),
        "output_sha256": sha256(OUTPUT),
        "database_mutations": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
