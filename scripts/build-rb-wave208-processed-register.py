#!/usr/bin/env python3
"""Merge the two completed 500-row B2B queues into a pinned register."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


FIELDS = [
    "product_external_id",
    "processed_wave",
    "priority_score",
    "name",
    "category_external_id",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(path: Path, expected_sha: str, expected_rows: int, label: str) -> list[dict[str, str]]:
    actual_sha = sha256(path)
    if actual_sha != expected_sha.lower():
        raise SystemExit(f"{label} SHA-256 mismatch: {actual_sha}")
    source = rows(path)
    if len(source) != expected_rows:
        raise SystemExit(f"{label} expected {expected_rows} rows, got {len(source)}")
    ids = [row.get("product_external_id", "").strip() for row in source]
    if any(not value for value in ids):
        raise SystemExit(f"{label} contains an empty product_external_id")
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{label} repeats product_external_id")
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wave174", type=Path, required=True)
    parser.add_argument("--wave205", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--expected-wave174-sha256", required=True)
    parser.add_argument("--expected-wave205-sha256", required=True)
    parser.add_argument("--expected-each-records", type=int, default=500)
    args = parser.parse_args()

    wave174 = validate(
        args.wave174,
        args.expected_wave174_sha256,
        args.expected_each_records,
        "Wave174",
    )
    wave205 = validate(
        args.wave205,
        args.expected_wave205_sha256,
        args.expected_each_records,
        "Wave205",
    )
    first_ids = {row["product_external_id"] for row in wave174}
    second_ids = {row["product_external_id"] for row in wave205}
    overlap = first_ids & second_ids
    if overlap:
        raise SystemExit("Wave174 and Wave205 overlap: " + ", ".join(sorted(overlap)[:5]))

    output_rows = []
    for wave, source in (("wave174", wave174), ("wave205", wave205)):
        for row in source:
            output_rows.append(
                {
                    "product_external_id": row["product_external_id"],
                    "processed_wave": wave,
                    "priority_score": row.get("priority_score", ""),
                    "name": row.get("name", ""),
                    "category_external_id": row.get("category_external_id", ""),
                }
            )
    if len(output_rows) != 1000 or len({row["product_external_id"] for row in output_rows}) != 1000:
        raise SystemExit("Processed register must contain exactly 1000 unique rows")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "schema_version": 1,
        "wave": "wave208",
        "input_records": {"wave174": len(wave174), "wave205": len(wave205)},
        "input_sha256": {
            "wave174": sha256(args.wave174),
            "wave205": sha256(args.wave205),
        },
        "input_overlap_records": 0,
        "processed_records": len(output_rows),
        "unique_product_external_ids": len({row["product_external_id"] for row in output_rows}),
        "processed_wave_counts": dict(sorted(Counter(row["processed_wave"] for row in output_rows).items())),
        "category_counts": dict(sorted(Counter(row["category_external_id"] for row in output_rows).items())),
        "output_sha256": sha256(args.output),
        "automatic_database_mutations": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
