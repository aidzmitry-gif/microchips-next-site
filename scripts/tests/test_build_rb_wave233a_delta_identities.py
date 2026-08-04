#!/usr/bin/env python3
"""Regression checks for the offline Wave233-A Delta identity packet."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("wave233a", ROOT / "scripts/build-rb-wave233a-delta-identities.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_packet() -> None:
    ledger, summary, manifest = MODULE.build(ROOT, ROOT)
    assert len(ledger) == 152
    assert summary["input_records"] == 152
    assert summary["pass_records"] == len(manifest["products"])
    assert summary["pass_records"] + summary["hold_records"] == 152
    assert len({row["external_id"] for row in ledger}) == len(ledger)
    for row in ledger:
        assert row["mpn"] in row["current_name"]
        if row["decision"] == "PASS":
            assert not row["hold_reason"] and not row["canonical_conflict_external_ids"]
            snapshot = ROOT / "docs/imports" / row["source_snapshot_path"]
            assert snapshot.is_file()
            assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]
        else:
            assert row["hold_reason"]
    assert all(product["manufacturer"] == "Delta" for product in manifest["products"])
    assert all(product["mpn"] for product in manifest["products"])
    with (ROOT / MODULE.LEDGER).open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 152
    assert json.loads((ROOT / MODULE.SUMMARY).read_text(encoding="utf-8"))["input_records"] == 152


if __name__ == "__main__":
    test_packet()
    print("Wave233-A Delta identity builder tests passed")
