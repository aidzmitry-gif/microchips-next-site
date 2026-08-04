#!/usr/bin/env python3
"""Close the non-General-Security Wave234-C remainder without inventing identities."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs/audits/generated/rb-wave234-c-remaining-ups-batteries.csv"
SOURCES = [
    ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave207-device-small-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.csv",
    ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.csv",
]
LEDGER = ROOT / "docs/audits/generated/rb-wave234c-residual-identity-holds.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234c-residual-identity-holds.summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def brand(name: str) -> str:
    for candidate in ("B.B. Battery", "Alarm Force", "Contact", "Optimus", "Casil", "Minamoto", "Liitokala", "Kiper"):
        if candidate.lower() in name.lower():
            return candidate
    if re.search(r"\bHRL\b", name):
        return "Unresolved HRL"
    if re.search(r"\bDTM\b", name):
        return "Unresolved DTM"
    return "Unresolved"


def main() -> None:
    required = [LANE, *SOURCES]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Required Wave234-C residual evidence is missing: {missing}")
    residual = [row for row in read_csv(LANE) if "General Security" not in row["name"]]
    if len(residual) != 37 or len({row["external_id"] for row in residual}) != 37:
        raise SystemExit(f"Wave234-C residual drift: rows={len(residual)}")

    evidence: dict[str, tuple[Path, dict[str, str]]] = {}
    # Later ledgers are more specific and intentionally supersede earlier generic reviews.
    for path in SOURCES:
        for row in read_csv(path):
            evidence[row["product_external_id"]] = (path, row)

    ledger = []
    for row in residual:
        hit = evidence.get(row["external_id"])
        if hit:
            source_path, source_row = hit
            reason = source_row.get("conflict_reason") or source_row.get("hold_reason") or "Saved evidence does not prove an exact collision-free identity."
            partition = "hold_prior_review"
        else:
            source_path, source_row = None, {}
            reason = "No saved SHA-pinned first-party source proves this exact offered manufacturer and model."
            partition = "hold_no_pinned_exact_primary_source"
        ledger.append({
            "external_id": row["external_id"], "name": row["name"], "manufacturer_candidate": brand(row["name"]),
            "partition": partition, "prior_evidence_path": source_path.relative_to(ROOT).as_posix() if source_path else "",
            "prior_partition": source_row.get("partition", ""), "prior_safe_to_apply": source_row.get("safe_to_apply", ""),
            "source_url": source_row.get("source_url", ""),
            "source_snapshot_path": source_row.get("snapshot_path", source_row.get("source_snapshot_path", "")),
            "source_snapshot_sha256": source_row.get("snapshot_sha256", source_row.get("source_snapshot_sha256", "")),
            "hold_reason": reason, "safe_to_apply": "false", "media_id": row["media_id"],
            "content_sha256": row["content_sha256"],
        })
    fields = list(ledger[0])
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    partitions = Counter(row["partition"] for row in ledger)
    brands = Counter(row["manufacturer_candidate"] for row in ledger)
    summary = {
        "schema_version": 1, "batch": "wave234c_residual_holds", "checked_at": "2026-07-29",
        "input": {"path": LANE.relative_to(ROOT).as_posix(), "sha256": sha256(LANE), "rows": len(residual)},
        "source_inventory": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in SOURCES],
        "partition_counts": dict(sorted(partitions.items())), "manufacturer_counts": dict(sorted(brands.items())),
        "exact_primary_pass_rows": 0,
        "output": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "policy": {"database_mutations": 0, "media_mutations": 0, "commercial_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "partitions": dict(sorted(partitions.items())), "pass_rows": 0}))


if __name__ == "__main__":
    main()
