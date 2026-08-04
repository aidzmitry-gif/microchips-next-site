from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234c-residual-holds.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave234c-residual-identity-holds.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234c-residual-identity-holds.summary.json"


def test_wave234c_residual_is_complete_deterministic_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == hashlib.sha256(LEDGER.read_bytes()).hexdigest()
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 37
    assert len({row["external_id"] for row in rows}) == 37
    assert all(row["safe_to_apply"] == "false" for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["partition_counts"] == {
        "hold_no_pinned_exact_primary_source": 24,
        "hold_prior_review": 13,
    }
    assert summary["exact_primary_pass_rows"] == 0
    assert summary["policy"]["database_mutations"] == 0
