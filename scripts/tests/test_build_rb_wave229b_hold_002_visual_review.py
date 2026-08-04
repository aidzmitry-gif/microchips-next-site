from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave229b-hold-002-visual-review.py"
OUTPUTS = (
    ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave229b-2026-07-29.json",
    ROOT / "docs/audits/generated/rb-wave229b-hold-002-visual-review.csv",
    ROOT / "docs/audits/generated/rb-wave229b-hold-002-visual-review.summary.json",
    ROOT / "docs/audits/2026-07-29-rb-wave229b-hold-002-visual-review.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave229b_is_deterministic_and_strict() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(digest(path) for path in OUTPUTS)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(digest(path) for path in OUTPUTS)

    manifest = json.loads(OUTPUTS[0].read_text(encoding="utf-8"))
    summary = json.loads(OUTPUTS[2].read_text(encoding="utf-8"))
    with OUTPUTS[1].open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert len(ledger) == 81 and len(manifest["images"]) == 36
    assert sum(row["verdict"] == "PASS" for row in ledger) == 36
    assert sum(row["reason"] == "visible_mpn_mismatch" for row in ledger) == 3
    assert all(row["identity_scope"] == "exact" and row["identity_evidence_level"] == "visible_exact_mpn" for row in manifest["images"])
    assert {row["external_id"] for row in manifest["images"]}.isdisjoint({"bitrix:2808", "bitrix:2831", "bitrix:2909"})
    assert summary["coverage"] == {"contact_sheets": 7, "ocr_hold_rows": 81, "visual_pass": 36, "visual_hold": 45, "visible_mpn_mismatches": 3}
    assert summary["safety"] == {"database_operations": 0, "apply_performed": False, "media_promotion_performed": False, "commit_or_push": False}
