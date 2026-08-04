from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave231c-corrected-sonnenschein-description-stage.py"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-stage-manifest-wave231c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave231c-corrected-sonnenschein-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave231c-corrected-sonnenschein-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave231c-corrected-sonnenschein-descriptions.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave231c_stages_only_the_two_corrected_legacy_drafts() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(digest(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(digest(path) for path in (MANIFEST, LEDGER, SUMMARY, REPORT))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert {row["external_id"] for row in manifest["products"]} == {"bitrix:2831", "bitrix:3117"}
    assert all(row["identity_scope"] == row["evidence_scope"] == "model_core" and row["model_core"] in {"S 12/17 G5", "S 12/6.6 S"} for row in manifest["products"])
    assert all(row["current_draft_status"] == "legacy_preview_applied" and row["refresh_existing"] == row["refresh_applied"] == "true" and row["safe_to_apply"] == "false" for row in ledger)
    assert summary["coverage"] == {"corrected_products": 2, "source_backed_complete_before": 0, "legacy_preview_applied_before": 2, "staged": 2, "exact_scope": 0, "model_core_scope": 2}
    assert summary["safety"]["database_operations"] == 0 and summary["safety"]["apply_performed"] is False
