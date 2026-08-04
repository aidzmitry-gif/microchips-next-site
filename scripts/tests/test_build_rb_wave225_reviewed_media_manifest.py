from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave225-reviewed-media-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave225-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_visual_review_manifest_is_deterministic_and_strict() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}

    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    images = payload["images"]
    assert payload["locale"] == "ru-BY"
    assert len(images) == len({row["external_id"] for row in images}) == 48
    assert len({row["media_id"] for row in images}) == 48
    assert {row["manufacturer"] for row in images if row["identity_scope"] == "model_core"} == {"Panasonic"}
    assert all(row["rights_basis"].startswith("Company-owned") for row in images)
    assert all(row["identity_evidence_level"] in {"visible_exact_mpn", "visible_exact_model_core"} for row in images)
    assert all("independent Windows OCR bounded-token check also passed" in row["visual_verification_note"] for row in images)
    prohibited = {"price", "availability", "publication", "source_asset_url"}
    assert all(not (prohibited & set(row)) for row in images)


def test_summary_does_not_claim_database_application() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["reviewed_images"] == 48
    assert summary["database_apply"] is False
    assert summary["manifest_sha256"] == digest(MANIFEST)
