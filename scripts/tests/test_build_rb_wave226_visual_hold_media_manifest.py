from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave226-visual-hold-media-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave226-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_hold_visual_manifest_is_deterministic_and_strict() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    images = payload["images"]
    assert payload["locale"] == "ru-BY"
    assert len(images) == len({row["external_id"] for row in images}) == 20
    assert len({row["media_id"] for row in images}) == 20
    assert {row["identity_scope"] for row in images} == {"model_core"}
    assert {row["manufacturer"] for row in images} == {"Panasonic"}
    assert all(row["rights_basis"].startswith("Company-owned") for row in images)
    assert all(row["identity_evidence_level"] == "visible_exact_model_core" for row in images)
    assert all("Manual machine-vision contact-sheet review confirmed the exact visible product marking" in row["visual_verification_note"] for row in images)
    assert all("OCR remained HOLD" in row["visual_verification_note"] for row in images)
    prohibited = {"price", "availability", "publication", "source_asset_url", "mpn"}
    assert all(not (prohibited & set(row)) for row in images)


def test_summary_records_holds_and_no_database_apply() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["reviewed_images"] == summary["allowlist_count"] == 20
    assert summary["ocr_required_verdict"] == "HOLD"
    assert summary["rejected_conflicts"] == [{
        "external_id": "bitrix:4091",
        "media_id": "2273",
        "expected_exact": "CR2",
        "observed_visible_marking": "CR123",
        "disposition": "rejected_visible_marking_mismatch",
    }]
    assert summary["database_apply"] is False
    assert summary["manifest_sha256"] == digest(MANIFEST)
    assert summary["ledger_sha256"] == digest(LEDGER)
