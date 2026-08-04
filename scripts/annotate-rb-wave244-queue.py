#!/usr/bin/env python3
"""Carry no-repeat statuses into the live queue after Wave244 duplicate retirement."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.summary.json"
EXPECTED_RETIRED = {
    "bitrix:3266", "bitrix:1511", "bitrix:1488",
    "bitrix:1542", "bitrix:23799", "bitrix:20088",
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    previous = read(PREVIOUS)
    live = read(OUTPUT)
    command_summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if command_summary.get("schema_version") == 1 and isinstance(command_summary.get("readiness"), dict):
        command_summary = command_summary["readiness"]
    prior = {row["product_external_id"]: row for row in previous}
    current = {row["product_external_id"]: row for row in live}
    if len(prior) != len(previous) or len(current) != len(live):
        raise RuntimeError("Queue product_external_id values must be unique")
    retired = set(prior) - set(current)
    added = set(current) - set(prior)
    if retired != EXPECTED_RETIRED or len(added) != len(retired):
        raise RuntimeError(f"Unexpected Wave244 membership drift: retired={sorted(retired)}, added={sorted(added)}")

    inherited = 0
    for row in live:
        external_id = row["product_external_id"]
        previous = prior.get(external_id)
        if previous is not None and previous.get("research_status") != "pending_official_source_research":
            row["research_status"] = previous["research_status"]
            inherited += 1
        elif external_id in added:
            row["research_status"] = "new_after_verified_duplicate_retirement_wave244"

    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(live[0]))
        writer.writeheader()
        writer.writerows(live)

    descriptions = sum(row["has_applied_description"] == "true" for row in live)
    summary = {
        "schema_version": 1,
        "rows": len(live),
        "description_present": descriptions,
        "description_missing": len(live) - descriptions,
        "verified_image_present": sum(row["has_verified_published_image"] == "true" for row in live),
        "retired_verified_duplicates": sorted(retired),
        "replacement_rows": sorted(added),
        "inherited_no_repeat_statuses": inherited,
        "new_replacement_rows_pending_research": len(added),
        "membership_policy": "live 10% queue after Wave244; prior no-repeat decisions inherited and only newly admitted replacements remain pending",
        "previous_queue_sha256": sha(PREVIOUS),
        "output_queue_sha256": sha(OUTPUT),
        "readiness": command_summary,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
