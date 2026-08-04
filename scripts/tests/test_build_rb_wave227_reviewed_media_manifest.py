from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave227-reviewed-media-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave227-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_wave227_pass_manifest_is_deterministic_and_exact() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    images = payload["images"]
    assert payload["locale"] == "ru-BY"
    assert len(images) == len({row["external_id"] for row in images}) == 75
    assert len({row["media_id"] for row in images}) == 75
    assert len({row["content_sha256"] for row in images}) == 75
    assert {row["identity_scope"] for row in images} == {"exact"}
    assert all(row["mpn"] for row in images)
    assert all(row["identity_evidence_level"] == "visible_exact_mpn" for row in images)
    assert all(row["rights_basis"].startswith("Company-owned") for row in images)
    assert all("OCR PASS and manual machine-vision contact-sheet review" in row["visual_verification_note"] for row in images)
    prohibited = {"price", "availability", "publication", "source_asset_url", "model_core", "manufacturer"}
    assert all(not (prohibited & set(row)) for row in images)


def test_summary_pins_all_sources_and_does_not_apply_to_database() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["reviewed_images"] == 75
    assert summary["ocr_required_verdict"] == "PASS"
    assert summary["batches"] == [
        {"batch": "001", "input_rows": 100, "pass_rows": 32},
        {"batch": "002", "input_rows": 100, "pass_rows": 19},
        {"batch": "003", "input_rows": 57, "pass_rows": 24},
    ]
    assert set(summary["input_sha256"]) == set(summary["review_sha256"]) == set(summary["contact_index_sha256"]) == {"001", "002", "003"}
    assert summary["manifest_sha256"] == digest(MANIFEST)
    assert summary["ledger_sha256"] == digest(LEDGER)
    assert summary["database_apply"] is False
