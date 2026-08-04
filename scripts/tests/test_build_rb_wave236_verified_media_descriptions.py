from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave236-verified-media-descriptions.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave236-verified-media-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave236-verified-media-descriptions.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave236-verified-media-descriptions.summary.json"


def test_wave236_package_is_complete_deterministic_and_primary_only() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    assert first == second

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {"bitrix:1526", "bitrix:1617", "bitrix:24551", "bitrix:2849", "bitrix:1464", "bitrix:1561", "bitrix:1789", "bitrix:1493"}
    assert {row["external_id"] for row in manifest["products"]} == expected
    assert {row["external_id"] for row in rows} == expected
    assert all(row["identity_scope"] == row["evidence_scope"] == "model_core" for row in manifest["products"])
    assert all(row["source_tier"] == "manufacturer_primary" and row["manufacturer_primary"] is True for row in manifest["products"])
    assert all(row["source_exact_model_present"] == "true" and row["decision"] == "STAGE" for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {"verified_image_missing_description": 8, "stage": 8, "hold": 0}
    assert summary["safety"]["commercial_changes"] == 0
