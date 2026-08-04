#!/usr/bin/env python3
"""Carry Wave244 no-repeat decisions into Wave245 and close reviewed replacements."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-enrichment-queue-wave245.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave245.summary.json"

REVIEWED = {
    "bitrix:1569": "source_backed_description_applied_wave245",
    "bitrix:1580": "source_backed_description_applied_wave245",
    "bitrix:1596": "source_backed_description_applied_wave245",
    "bitrix:3232": "source_backed_description_applied_wave245",
    "bitrix:1598": "hold_two_exact_1c_candidates_wave245",
    "bitrix:1159": "hold_no_new_exact_primary_source_wave245",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    previous_rows = read_rows(PREVIOUS)
    current_rows = read_rows(OUTPUT)
    previous = {row["product_external_id"]: row for row in previous_rows}
    current = {row["product_external_id"]: row for row in current_rows}
    if len(previous) != len(previous_rows) or len(current) != len(current_rows):
        raise RuntimeError("Queue product_external_id values must be unique")
    if set(previous) != set(current):
        raise RuntimeError("Wave245 queue membership changed unexpectedly")
    missing_reviewed = set(REVIEWED) - set(current)
    if missing_reviewed:
        raise RuntimeError(f"Reviewed Wave245 rows left the queue: {sorted(missing_reviewed)}")

    for row in current_rows:
        external_id = row["product_external_id"]
        row["research_status"] = REVIEWED.get(
            external_id,
            previous[external_id]["research_status"],
        )

    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(current_rows[0]))
        writer.writeheader()
        writer.writerows(current_rows)

    command_summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if command_summary.get("schema_version") == 1 and isinstance(command_summary.get("readiness"), dict):
        command_summary = command_summary["readiness"]
    statuses = Counter(row["research_status"] for row in current_rows)
    result = {
        "schema_version": 1,
        "rows": len(current_rows),
        "description_present": sum(row["has_applied_description"] == "true" for row in current_rows),
        "description_missing": sum(row["has_applied_description"] != "true" for row in current_rows),
        "verified_image_present": sum(row["has_verified_published_image"] == "true" for row in current_rows),
        "reviewed_replacement_rows": REVIEWED,
        "reviewed_applied": sum(value.startswith("source_backed") for value in REVIEWED.values()),
        "reviewed_hold": sum(value.startswith("hold_") for value in REVIEWED.values()),
        "membership_change": 0,
        "research_status_distribution": dict(sorted(statuses.items())),
        "previous_queue_sha256": sha256(PREVIOUS),
        "output_queue_sha256": sha256(OUTPUT),
        "readiness": command_summary,
    }
    SUMMARY.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
