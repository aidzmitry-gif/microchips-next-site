#!/usr/bin/env python3
"""Produce a fail-closed handoff for unreviewed industrial replacement packs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

BATCHES = (
    (
        "cameron_sino_exact_model",
        re.compile(r"\bCS-[A-Z0-9]", re.I),
        "Cameron Sino official exact-model catalogue",
        "replacement_pack_identity_and_specs",
        "exact replacement manufacturer and model evidence required",
    ),
    (
        "zebra_legacy_mobile_computers",
        re.compile(r"\b(?:Zebra|Motorola|Symbol)\b", re.I),
        "Zebra official accessories, parts and service documentation",
        "device_compatibility_context_only",
        "OEM evidence must not set replacement-pack manufacturer or MPN",
    ),
    (
        "honeywell_mobile_computers",
        re.compile(r"\bHoneywell\b", re.I),
        "Honeywell official mobility accessories and service documentation",
        "device_compatibility_context_only",
        "OEM evidence must not set replacement-pack manufacturer or MPN",
    ),
    (
        "datalogic_data_capture",
        re.compile(r"\bDatalogic\b", re.I),
        "Datalogic official product accessories and service documentation",
        "device_compatibility_context_only",
        "OEM evidence must not set replacement-pack manufacturer or MPN",
    ),
    (
        "intermec_mobile_computers",
        re.compile(r"\bIntermec\b", re.I),
        "Honeywell/Intermec official product and service documentation",
        "device_compatibility_context_only",
        "OEM evidence must not set replacement-pack manufacturer or MPN",
    ),
)
REQUIRED = {"product_external_id", "name", "category_external_id", "safe_to_apply"}


def load(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def build(queue: Path, exclusions: Path, output: Path, summary_path: Path, expected_records: int = 500) -> dict[str, object]:
    rows = load(queue, REQUIRED)
    if len(rows) != expected_records or len({row["product_external_id"] for row in rows}) != len(rows):
        raise ValueError("queue count or product_external_id uniqueness mismatch")
    if any(row["category_external_id"] != "seo:batteries-industrial" or row["safe_to_apply"].strip().casefold() != "false" for row in rows):
        raise ValueError("queue must remain industrial and safe_to_apply=false")
    excluded_rows = load(exclusions, {"external_id", "reason"})
    excluded = {row["external_id"].strip() for row in excluded_rows}
    if "" in excluded or len(excluded) != len(excluded_rows):
        raise ValueError("exclusions must contain unique nonblank external_id")
    available = [row for row in rows if row["product_external_id"] not in excluded]
    output_rows: list[dict[str, str]] = []
    assigned: set[str] = set()
    for batch, pattern, route, evidence_class, evidence_boundary in BATCHES:
        members = [row for row in available if row["product_external_id"] not in assigned and pattern.search(row["name"])]
        assigned.update(row["product_external_id"] for row in members)
        for row in members:
            output_rows.append({
                "batch": batch,
                "product_external_id": row["product_external_id"],
                "name": row["name"],
                "source_route": route,
                "evidence_class": evidence_class,
                "evidence_boundary": evidence_boundary,
                "safe_to_apply": "false",
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "batch",
            "product_external_id",
            "name",
            "source_route",
            "evidence_class",
            "evidence_boundary",
            "safe_to_apply",
        ])
        writer.writeheader(); writer.writerows(output_rows)
    batch_counts = Counter(row["batch"] for row in output_rows)
    summary = {"queue_path": str(queue), "queue_sha256": hashlib.sha256(queue.read_bytes()).hexdigest(), "queue_records": len(rows), "excluded_records": len(rows) - len(available), "available_records": len(available), "recommended_batch_records": len(output_rows), "recommended_batches": dict(sorted(batch_counts.items())), "unassigned_records": len(available) - len(output_rows), "automatic_database_mutations": 0, "safe_to_apply_records": 0}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True); parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--summary", type=Path, required=True); parser.add_argument("--expected-records", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps(build(args.queue, args.exclusions, args.output, args.summary, args.expected_records), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
