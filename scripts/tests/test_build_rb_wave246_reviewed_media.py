import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave246.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave246-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246-reviewed-media.summary.json"


def test_wave246_review_manifest_is_complete_deterministic_and_fail_closed():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build-rb-wave246-reviewed-media.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(rows) == 16
    assert sum(row["visual_decision"] == "PASS_VISIBLE_EXACT_MPN" for row in rows) == 11
    assert sum(row["visual_decision"] == "HOLD" for row in rows) == 5
    assert len(manifest["images"]) == 11
    assert all(image["identity_scope"] == "exact" for image in manifest["images"])
    assert all(image["identity_evidence_level"] == "visible_exact_mpn" for image in manifest["images"])
    assert all("Company-owned" in image["rights_basis"] for image in manifest["images"])
    assert {image["external_id"] for image in manifest["images"]}.isdisjoint({
        "bitrix:3190", "bitrix:1138", "bitrix:1580", "bitrix:1596", "bitrix:23844",
    })
    assert summary["reviewed_rows"] == 16
    assert summary["visual_pass"] == 11
    assert summary["visual_hold"] == 5
    assert hashlib.sha256(MANIFEST.read_bytes()).hexdigest() == summary["manifest_sha256"]
    assert summary["database_apply"] is False
