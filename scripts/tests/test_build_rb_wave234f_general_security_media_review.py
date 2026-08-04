from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234f-general-security-media-review.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave234f-general-security-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave234f-general-security-media-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234f-general-security-media-review.summary.json"


def test_wave234f_media_review_is_deterministic_complete_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), hashlib.sha256(LEDGER.read_bytes()).hexdigest())
    assert first == second
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 29 and len(manifest["images"]) == 26
    assert {row["external_id"] for row in rows if row["visual_decision"] == "HOLD"} == {"bitrix:3034", "bitrix:3135", "bitrix:3268"}
    assert not {"bitrix:3034", "bitrix:3135", "bitrix:3268"}.intersection(row["external_id"] for row in manifest["images"])
    assert all(row["identity_evidence_level"] == "visible_exact_mpn" for row in manifest["images"])
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {"identity_rows": 29, "ocr_pass": 9, "visual_pass": 26, "visual_holds": 3}
    assert summary["safety"]["price_or_stock_changes"] == 0
