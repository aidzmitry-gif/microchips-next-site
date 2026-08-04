from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234a-panasonic-mnb-review.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave234a-panasonic-mnb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234a-panasonic-mnb-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234a-panasonic-mnb-2026-07-29.json"


def test_wave234a_is_complete_deterministic_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert first == second
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 56
    assert len({row["external_id"] for row in rows}) == 56
    assert all(row["wave234_decision"] == "HOLD" and row["safe_to_apply"] == "false" for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["partition_counts"] == {"conflict": 1, "no_evidence": 55}
    assert summary["covered_rows"] == 56
    assert json.loads(MANIFEST.read_text(encoding="utf-8"))["products"] == []
