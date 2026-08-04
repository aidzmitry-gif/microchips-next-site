#!/usr/bin/env python3
"""Consolidate existing pinned evidence for the Wave234-A Panasonic/MNB lane."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs/audits/generated/rb-wave234-a-panasonic-mnb.csv"
SOURCES = [
    ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.csv",
]
LEDGER = ROOT / "docs/audits/generated/rb-wave234a-panasonic-mnb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234a-panasonic-mnb-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234a-panasonic-mnb-2026-07-29.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [LANE, *SOURCES]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Required Wave234-A evidence is missing: {missing}")
    lane = read_csv(LANE)
    if len(lane) != 56 or len({row["external_id"] for row in lane}) != 56:
        raise SystemExit(f"Wave234-A input drift: rows={len(lane)}")

    evidence: dict[str, tuple[Path, dict[str, str]]] = {}
    for path in SOURCES:
        for row in read_csv(path):
            external_id = row["product_external_id"]
            if external_id in evidence:
                raise SystemExit(f"Wave234-A source overlap: {external_id}")
            evidence[external_id] = (path, row)
    missing_ids = sorted(row["external_id"] for row in lane if row["external_id"] not in evidence)
    if missing_ids:
        raise SystemExit(f"Wave234-A evidence coverage drift: {missing_ids}")

    selected = [(lane_row, *evidence[lane_row["external_id"]]) for lane_row in lane]
    partitions = Counter(row["partition"] for _, _, row in selected)
    if partitions != Counter({"no_evidence": 55, "conflict": 1}):
        raise SystemExit(f"Wave234-A partition drift: {dict(partitions)}")
    if any(row.get("safe_to_apply", "").lower() == "true" or row["partition"] == "exact_safe" for _, _, row in selected):
        raise SystemExit("Wave234-A now contains an exact-safe row; manual promotion review is required")

    fields = [
        "external_id", "name", "source_file", "source_file_sha256", "partition",
        "source_tier", "source_publisher", "source_url", "snapshot_path",
        "snapshot_sha256", "conflict_reason", "safe_to_apply", "wave234_decision",
        "media_id", "content_sha256",
    ]
    ledger = []
    for lane_row, source_path, row in selected:
        ledger.append({
            "external_id": lane_row["external_id"], "name": lane_row["name"],
            "source_file": source_path.relative_to(ROOT).as_posix(), "source_file_sha256": sha256(source_path),
            "partition": row["partition"], "source_tier": row.get("source_tier", ""),
            "source_publisher": row.get("source_publisher", ""), "source_url": row.get("source_url", ""),
            "snapshot_path": row.get("snapshot_path", row.get("source_snapshot_path", "")),
            "snapshot_sha256": row.get("snapshot_sha256", row.get("source_snapshot_sha256", "")),
            "conflict_reason": row.get("conflict_reason", ""), "safe_to_apply": row.get("safe_to_apply", ""),
            "wave234_decision": "HOLD", "media_id": lane_row["media_id"],
            "content_sha256": lane_row["content_sha256"],
        })
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    manifest = {
        "schema_version": 1, "site_key": "microchips-by", "review_batch": "wave234a_panasonic_mnb",
        "checked_at": "2026-07-29", "products": [],
        "note": "No PASS rows: saved evidence does not prove a collision-free exact current identity.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1, "batch": "wave234a_panasonic_mnb", "checked_at": "2026-07-29",
        "input": {"path": LANE.relative_to(ROOT).as_posix(), "sha256": sha256(LANE), "rows": len(lane)},
        "source_inventory": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in SOURCES],
        "covered_rows": len(ledger), "partition_counts": dict(sorted(partitions.items())), "exact_primary_pass_rows": 0,
        "output": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 0},
        "policy": {"database_mutations": 0, "media_mutations": 0, "commercial_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "partitions": dict(sorted(partitions.items())), "pass_rows": 0}))


if __name__ == "__main__":
    main()
