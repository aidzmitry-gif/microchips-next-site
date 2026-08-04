#!/usr/bin/env python3
"""Audit the Wave233 Fiamm identity candidate bundle without touching the DB."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv"
LIVE = ROOT / "docs/audits/generated/rb-wave233-fiamm-live-identity-collisions.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-fiamm-identity-candidates-wave233-2026-07-29.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    if len(ledger) != 106 or len({row["external_id"] for row in ledger}) != 106:
        raise SystemExit("ledger no longer has the exact frozen 106-card target")
    if summary["ledger"]["sha256"] != sha256(LEDGER) or summary["manifest"]["sha256"] != sha256(MANIFEST):
        raise SystemExit("summary hash drift")
    if live.get("mode") != "read_only" or live.get("database_mutations") != 0 or live.get("candidate_rows_checked") != 106:
        raise SystemExit("live collision evidence is not a 106-row read-only guard")
    safe = [row for row in ledger if row["safe_to_apply"] == "true"]
    if {row["external_id"] for row in safe} != {row["external_id"] for row in manifest["products"]}:
        raise SystemExit("manifest and ledger safe set disagree")
    if any(not row["local_exact_text"] == "true" or row["normalized_mpn_sku_conflict_ids"] for row in safe):
        raise SystemExit("manifest contains unproven or colliding MPN")
    if len({norm(row["mpn"]) for row in manifest["products"]}) != len(manifest["products"]):
        raise SystemExit("manifest normalized MPN is not unique")
    if not summary["manifest"]["review_only"] or not summary["policy"]["saved_fiamm_distributor_sources_are_identity_evidence_not_apply_authority"]:
        raise SystemExit("authority policy weakened")
    print(json.dumps({"rows": len(ledger), "manifest_rows": len(manifest["products"]), "holds": len(ledger) - len(safe), "audit": "ok"}))


if __name__ == "__main__":
    main()
