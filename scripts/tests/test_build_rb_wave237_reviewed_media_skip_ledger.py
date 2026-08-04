from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave237-reviewed-media-skip-ledger.py"
OUTPUT = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.summary.json"


def test_wave237_skip_ledger_is_deterministic_unique_and_complete() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == first
    with OUTPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    keys = [(row["external_id"], row["media_id"]) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(row["review_ledgers"] for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_ledgers"] == 13
    assert summary["unique_reviewed_media"] == len(rows)
    assert summary["database_operations"] == 0
