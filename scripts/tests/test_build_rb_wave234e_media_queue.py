from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234e-media-queue.py"
QUEUE = ROOT / "docs/audits/generated/rb-wave234e-general-security-media-queue.csv"
LEDGER = ROOT / "docs/audits/generated/rb-wave234e-empty-reviewed-media-ledger.csv"


def test_wave234e_queue_is_bounded_deterministic_and_exact() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = hashlib.sha256(QUEUE.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == hashlib.sha256(QUEUE.read_bytes()).hexdigest()
    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 29
    assert len({row["product_external_id"] for row in rows}) == 29
    assert all(row["mpn"] and not row["model_core"] for row in rows)
    assert LEDGER.read_text(encoding="utf-8") == "external_id,media_id\n"
