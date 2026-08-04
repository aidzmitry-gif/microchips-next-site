from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave233d-delta-media-review.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave233d-delta-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave233d-delta-media-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233d-delta-media-review.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave233d-delta-media-review.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave233d_is_deterministic_and_fail_closed() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(sha256(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(sha256(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert len(manifest["images"]) == 15
    assert len(ledger) == 16
    assert [(row["external_id"], row["expected_mpn"]) for row in ledger if row["decision"] == "HOLD"] == [("bitrix:2952", "DT 6033")]
    assert all(row["identity_scope"] == "exact" and row["identity_evidence_level"] == "visible_exact_mpn" for row in manifest["images"])
    assert len({row["media_id"] for row in manifest["images"]}) == 15
    assert len({row["content_sha256"] for row in manifest["images"]}) == 15
    assert summary["coverage"] == {"identity_rows": 16, "ocr_and_visual_pass": 15, "holds": 1}
    assert summary["safety"] == {"database_operations": 0, "apply_performed": False, "media_changes": 0, "price_or_stock_changes": 0}
