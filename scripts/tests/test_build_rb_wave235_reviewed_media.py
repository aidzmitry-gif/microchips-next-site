from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave235-reviewed-media.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave235-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave235-reviewed-media.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave235-reviewed-media.summary.json"


def test_wave235_review_is_deterministic_complete_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    assert first == second

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    passed = {row["external_id"] for row in rows if row["visual_decision"] == "PASS"}
    assert len(rows) == 117 and len(manifest["images"]) == 9
    assert passed == {
        "bitrix:11753", "bitrix:1464", "bitrix:1493", "bitrix:1526", "bitrix:1561",
        "bitrix:1617", "bitrix:24551", "bitrix:2952", "bitrix:4776",
    }
    assert sum(row["batch_status"] == "hold" for row in rows) == 47
    assert all(row["identity_evidence_level"] == "visible_exact_mpn" for row in manifest["images"])
    assert len({row["content_sha256"] for row in manifest["images"]}) == 9
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {
        "exported": 117,
        "shared_binary_holds": 47,
        "unique_binary_reviewed": 70,
        "ocr_pass": 0,
        "visual_pass": 9,
        "visual_holds": 108,
    }
    assert summary["safety"]["price_or_stock_changes"] == 0
