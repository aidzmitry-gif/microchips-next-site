#!/usr/bin/env python3
"""Freeze the live Wave243 queue with content no-repeat annotations."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / "docs/audits/generated/rb-enrichment-queue-wave242.csv"
LIVE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243-live.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243.summary.json"
LEDGERS = (
    ROOT / "docs/audits/generated/rb-wave243a-delta-evidence-ledger.csv",
    ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description-ledger.csv",
    ROOT / "docs/audits/generated/rb-wave243c-remaining-description-ledger.csv",
)
EXPECTED_RETIRED = {
    "bitrix:1400", "bitrix:1401", "bitrix:1556", "bitrix:2915", "bitrix:20151",
}
EXPECTED_ADDED = {
    "bitrix:1155", "bitrix:1143", "bitrix:3204", "bitrix:1591", "bitrix:3139",
}


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ledger_statuses() -> dict[str, str]:
    statuses: dict[str, str] = {}
    for path in LEDGERS:
        for row in read(path):
            external_id = row.get("external_id", "").strip()
            if not external_id:
                raise RuntimeError(f"{path.name} contains an empty external_id")
            decision = row.get("decision", "").strip().upper()
            reason = (row.get("hold_reason") or row.get("partition") or "reviewed").strip().lower()
            status = "description_verified_media_pending" if decision == "PASS" else f"content_{reason}_media_pending"
            prior = statuses.get(external_id)
            if prior is not None and prior != status:
                raise RuntimeError(f"Conflicting Wave243 research status for {external_id}")
            statuses[external_id] = status
    return statuses


def main() -> None:
    previous = read(PREVIOUS)
    live = read(LIVE)
    previous_ids = {row["product_external_id"] for row in previous}
    live_ids = {row["product_external_id"] for row in live}
    if len(previous_ids) != len(previous) or len(live_ids) != len(live):
        raise RuntimeError("Queue product_external_id values must be unique")
    retired = previous_ids - live_ids
    added = live_ids - previous_ids
    if retired != EXPECTED_RETIRED or added != EXPECTED_ADDED:
        raise RuntimeError(f"Unexpected Wave243 membership drift: retired={sorted(retired)}, added={sorted(added)}")

    statuses = ledger_statuses()
    annotated = 0
    for row in live:
        status = statuses.get(row["product_external_id"])
        if status is not None:
            row["research_status"] = status
            annotated += 1
    # These five rows entered the fixed-size queue only after verified Delta
    # duplicates retired. They were outside the frozen Wave243 research scope,
    # so mark them explicitly as new work instead of pretending they were held.
    for row in live:
        if row["product_external_id"] in EXPECTED_ADDED:
            if row["product_external_id"] in statuses:
                raise RuntimeError("A replacement row unexpectedly overlaps the frozen Wave243 research scope")
            row["research_status"] = "new_after_verified_duplicate_retirement"

    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(live[0]))
        writer.writeheader()
        writer.writerows(live)

    description_present = sum(row["has_applied_description"] == "true" for row in live)
    payload = {
        "schema_version": 1,
        "rows": len(live),
        "description_present": description_present,
        "description_missing": len(live) - description_present,
        "verified_image_present": sum(row["has_verified_published_image"] == "true" for row in live),
        "retired_verified_duplicates": sorted(retired),
        "replacement_rows": sorted(added),
        "wave243_content_status_annotated": annotated,
        "new_replacement_rows_pending_research": len(added),
        "membership_policy": "live 10% readiness queue; exact duplicate retirements replaced deterministically; Wave243 content decisions annotated so they are not researched again",
        "previous_queue_sha256": digest(PREVIOUS),
        "live_queue_sha256": digest(LIVE),
        "output_queue_sha256": digest(OUTPUT),
    }
    SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
