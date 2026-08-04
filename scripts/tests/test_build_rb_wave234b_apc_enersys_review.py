from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234b-apc-enersys-review.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave234b-apc-enersys-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234b-apc-enersys-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234b-apc-enersys-2026-07-29.json"


def test_wave234b_is_complete_deterministic_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert first == second

    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 34
    assert len({row["product_external_id"] for row in rows}) == 34
    assert all(row["wave234_decision"] == "HOLD" for row in rows)
    assert all(row["safe_to_apply"] == "false" for row in rows)

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert summary["partition_counts"] == {"compatibility": 1, "conflict": 8, "no_evidence": 25}
    assert summary["exact_primary_pass_rows"] == 0
    assert summary["evidence"]["covered_rows"] == 34
    assert manifest["products"] == []
