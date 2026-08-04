#!/usr/bin/env python3
"""Fail-closed verification for the no-repeat Wave208 priority queue."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


AUTOMOTIVE = re.compile(
    r"автомоб|авто[- ]?аккум|стартерн|мотоцикл|мопед|для\s+легков|для\s+грузов",
    re.I,
)
ELECTRONICS = re.compile(
    r"микросхем|транзистор|резистор|конденсатор|диод|тиристор|симистор|"
    r"микроконтроллер|полупроводник",
    re.I,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pinned(path: Path, expected: str, label: str) -> list[dict[str, str]]:
    actual = sha256(path)
    if actual != expected.lower():
        raise SystemExit(f"{label} SHA-256 mismatch: {actual}")
    return rows(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--builder-summary", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--expected-queue-sha256", required=True)
    parser.add_argument("--expected-processed-sha256", required=True)
    parser.add_argument("--expected-queue-records", type=int, default=500)
    parser.add_argument("--expected-processed-records", type=int, default=1000)
    args = parser.parse_args()

    queue = pinned(args.queue, args.expected_queue_sha256, "queue")
    processed = pinned(args.processed, args.expected_processed_sha256, "processed")
    queue_ids = [row.get("product_external_id", "") for row in queue]
    processed_ids = [row.get("product_external_id", "") for row in processed]
    if len(queue) != args.expected_queue_records or len(queue_ids) != len(set(queue_ids)):
        raise SystemExit("queue must contain exactly the expected number of unique IDs")
    if len(processed) != args.expected_processed_records or len(processed_ids) != len(set(processed_ids)):
        raise SystemExit("processed register must contain exactly the expected number of unique IDs")
    overlap = set(queue_ids) & set(processed_ids)
    if overlap:
        raise SystemExit("queue overlaps processed register: " + ", ".join(sorted(overlap)[:5]))

    automotive = [row for row in queue if AUTOMOTIVE.search(row.get("name", ""))]
    electronics = [row for row in queue if ELECTRONICS.search(row.get("name", ""))]
    if automotive or electronics:
        raise SystemExit(
            f"out-of-scope rows: automotive={len(automotive)}, electronics={len(electronics)}"
        )
    if any(row.get("safe_to_apply", "").lower() != "false" for row in queue):
        raise SystemExit("Wave208 queue contains a safe_to_apply row")

    builder_summary = json.loads(args.builder_summary.read_text(encoding="utf-8"))
    if builder_summary.get("output_sha256") != sha256(args.queue):
        raise SystemExit("builder summary does not pin the queue")
    if builder_summary.get("processed_sha256") != sha256(args.processed):
        raise SystemExit("builder summary does not pin the processed register")
    if builder_summary.get("automatic_database_mutations") != 0:
        raise SystemExit("builder summary reports a database mutation")

    summary = {
        "schema_version": 1,
        "wave": "wave208",
        "queue_records": len(queue),
        "queue_unique_product_external_ids": len(set(queue_ids)),
        "processed_records": len(processed),
        "processed_unique_product_external_ids": len(set(processed_ids)),
        "processed_overlap_records": 0,
        "automotive_records": 0,
        "electronics_records": 0,
        "safe_to_apply_records": 0,
        "category_counts": dict(sorted(Counter(row.get("category_external_id", "") for row in queue).items())),
        "readiness_counts": dict(sorted(Counter(row.get("readiness_class", "") for row in queue).items())),
        "queue_sha256": sha256(args.queue),
        "processed_sha256": sha256(args.processed),
        "builder_summary_sha256": sha256(args.builder_summary),
        "eligible_unreviewed_unprocessed": builder_summary["eligible_unreviewed_unprocessed"],
        "automatic_web_requests": 0,
        "automatic_database_mutations": 0,
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
