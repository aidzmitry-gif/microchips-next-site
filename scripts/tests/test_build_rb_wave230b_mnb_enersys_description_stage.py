from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave230b-mnb-enersys-description-stage.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-stage-manifest-wave230b-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave230b-mnb-enersys-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave230b-mnb-enersys-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave230b-mnb-enersys-descriptions.md"
OUTPUTS = (MANIFEST, LEDGER, SUMMARY, REPORT)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave230b_is_frozen_deterministic_and_model_core_only() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(digest(path) for path in OUTPUTS)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(digest(path) for path in OUTPUTS)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert len(manifest["products"]) == len(ledger) == 25
    assert {row["manufacturer"] for row in manifest["products"]} == {"MNB", "EnerSys"}
    assert sum(row["manufacturer"] == "MNB" for row in manifest["products"]) == 13
    assert sum(row["manufacturer"] == "EnerSys" for row in manifest["products"]) == 12
    assert all(row["identity_scope"] == row["evidence_scope"] == "model_core" for row in manifest["products"])
    assert all(row["name_ends_with_mpn"] == "false" and row["safe_to_apply"] == "false" for row in ledger)
    assert summary["coverage"] == {"frozen_wave230_targets": 25, "mnb_targets": 13, "enersys_targets": 12, "verified_media_lineage": 25, "staged": 25, "holds": 0, "exact_scope": 0, "model_core_scope": 25}
    assert summary["safety"]["database_operations"] == 0 and summary["safety"]["apply_performed"] is False
