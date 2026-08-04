#!/usr/bin/env python3
"""Materialize the fail-closed Wave234-B APC/EnerSys identity review.

The lane is deliberately derived from the pinned Wave209-A evidence ledger.
Only an ``exact_safe`` row could become an apply candidate.  The current lane
contains conflicts, non-exact pages, and one family-level compatibility row,
so the generated apply manifest is intentionally empty.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs/audits/generated/rb-wave234-b-apc-enersys.csv"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.csv"
LEDGER = ROOT / "docs/audits/generated/rb-wave234b-apc-enersys-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234b-apc-enersys-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234b-apc-enersys-2026-07-29.json"

EXPECTED_ROWS = 34
EXPECTED_PARTITIONS = {"compatibility": 1, "conflict": 8, "no_evidence": 25}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not LANE.is_file() or not EVIDENCE.is_file():
        raise SystemExit("Wave234-B lane or pinned Wave209-A evidence is missing")

    lane = read_csv(LANE)
    evidence_rows = read_csv(EVIDENCE)
    evidence = {row["product_external_id"]: row for row in evidence_rows}
    if len(lane) != EXPECTED_ROWS or len({row["external_id"] for row in lane}) != EXPECTED_ROWS:
        raise SystemExit(f"Wave234-B input drift: rows={len(lane)}")
    missing = sorted(row["external_id"] for row in lane if row["external_id"] not in evidence)
    if missing:
        raise SystemExit(f"Wave234-B evidence coverage drift: {missing}")

    selected = [evidence[row["external_id"]] for row in lane]
    partitions = Counter(row["partition"] for row in selected)
    if dict(sorted(partitions.items())) != EXPECTED_PARTITIONS:
        raise SystemExit(f"Wave234-B evidence partition drift: {dict(partitions)}")
    unsafe = [row for row in selected if row["safe_to_apply"].lower() == "true" or row["partition"] == "exact_safe"]
    if unsafe:
        raise SystemExit("Wave234-B now contains exact-safe evidence; review before generating an apply manifest")

    lane_by_id = {row["external_id"]: row for row in lane}
    fields = list(evidence_rows[0]) + ["wave234_name", "wave234_media_id", "wave234_content_sha256", "wave234_decision"]
    ledger = []
    for row in selected:
        lane_row = lane_by_id[row["product_external_id"]]
        ledger.append({
            **row,
            "wave234_name": lane_row["name"],
            "wave234_media_id": lane_row["media_id"],
            "wave234_content_sha256": lane_row["content_sha256"],
            "wave234_decision": "HOLD",
        })
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "review_batch": "wave234b_apc_enersys",
        "checked_at": "2026-07-29",
        "products": [],
        "note": "No PASS rows: exact first-party identity proof and collision clearance are both required.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    reasons = Counter(row["conflict_reason"] for row in selected)
    summary = {
        "schema_version": 1,
        "batch": "wave234b_apc_enersys",
        "checked_at": "2026-07-29",
        "input": {"path": LANE.relative_to(ROOT).as_posix(), "sha256": sha256(LANE), "rows": len(lane)},
        "evidence": {"path": EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(EVIDENCE), "covered_rows": len(selected)},
        "partition_counts": dict(sorted(partitions.items())),
        "hold_reason_counts": dict(sorted(reasons.items())),
        "exact_primary_pass_rows": 0,
        "output": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 0},
        "policy": {"database_mutations": 0, "media_mutations": 0, "commercial_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "partitions": dict(sorted(partitions.items())), "pass_rows": 0}))


if __name__ == "__main__":
    main()
