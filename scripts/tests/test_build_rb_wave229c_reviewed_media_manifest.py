from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave229c-reviewed-media-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave229c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave229c.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave229c.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave229c_manifest_is_deterministic_and_exact_only() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    images = payload["images"]
    assert payload["locale"] == "ru-BY"
    assert len(images) == len({row["external_id"] for row in images}) == 26
    assert len({row["media_id"] for row in images}) == 26
    assert {row["identity_scope"] for row in images} == {"exact"}
    assert all(row["mpn"] and row["identity_evidence_level"] == "visible_exact_mpn" for row in images)
    assert all(row["rights_basis"].startswith("Company-owned") for row in images)
    prohibited = {"price", "availability", "publication", "source_asset_url", "model_core", "manufacturer"}
    assert all(not (prohibited & set(row)) for row in images)


def test_wave229c_summary_keeps_all_holds_and_rejections_out_of_manifest() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    promoted = {row["external_id"] for row in payload["images"]}
    rejected = {row["external_id"] for row in summary["rejected_rows"]}
    assert summary["reviewed_contact_rows"] == 33
    assert summary["promoted_images"] == 26
    assert len(rejected) == 7
    assert summary["ocr_required_verdict"] == "HOLD"
    assert not (promoted & rejected)
    assert {"bitrix:3056", "bitrix:3099", "bitrix:3219"} <= rejected
    assert all(row["disposition"].startswith("rejected_") for row in summary["rejected_rows"])
    assert summary["manifest_sha256"] == digest(MANIFEST)
    assert summary["ledger_sha256"] == digest(LEDGER)
    assert summary["database_apply"] is False
