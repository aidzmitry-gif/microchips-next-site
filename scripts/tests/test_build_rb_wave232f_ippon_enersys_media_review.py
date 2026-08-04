from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave232f-ippon-enersys-media-review.py"
MANIFEST = ROOT / "docs/imports/rb-legacy-exact-preview-media-wave232f-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave232f-ippon-enersys-media-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232f-ippon-enersys-media-review.summary.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_twice() -> dict[Path, str]:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = {path: digest(path) for path in (MANIFEST, LEDGER, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == {path: digest(path) for path in first}
    return first


def test_wave232f_manifest_is_deterministic_and_uses_only_visible_exact_mpn() -> None:
    build_twice()
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(payload) == {"locale", "images"}
    assert payload["locale"] == "ru-BY"
    assert len(payload["images"]) == 1
    row = payload["images"][0]
    assert row["external_id"] == "bitrix:26048"
    assert row["media_id"] == 1566
    assert row["mpn"] == "12V70"
    assert row["identity_scope"] == "exact"
    assert row["identity_evidence_level"] == "visible_exact_mpn"
    assert row["rights_basis"] == "Company-owned Microchips legacy Bitrix upload backup."
    assert "source_asset_url" not in row and "official_identity_url" not in row
    assert "12V70" in row["visual_verification_note"]


def test_wave232f_holds_all_ippon_generic_product_images_even_with_official_identity() -> None:
    build_twice()
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = {row["external_id"]: row for row in csv.DictReader(handle)}
    held = {external_id for external_id, row in rows.items() if row["review_verdict"] == "HOLD"}
    assert held == {"bitrix:25120", "bitrix:25135", "bitrix:25149"}
    for external_id in held:
        row = rows[external_id]
        assert row["disposition"] == "hold_no_exact_visible_mpn"
        assert row["ocr_verdict"] == "HOLD"
        assert "official IPPON" in row["official_identity_evidence"]
        assert "cannot replace visible exact-MPN proof" in row["visual_review"]
    assert rows["bitrix:26048"]["review_verdict"] == "PASS"


def test_wave232f_summary_has_no_database_apply_or_external_asset_use() -> None:
    digests = build_twice()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["reviewed_rows"] == 4
    assert summary["promoted_images"] == 1
    assert summary["held_rows"] == ["bitrix:25120", "bitrix:25135", "bitrix:25149"]
    assert summary["database_apply"] is False
    assert summary["official_assets_used"] is False
    assert summary["manifest_sha256"] == digests[MANIFEST]
    assert summary["ledger_sha256"] == digests[LEDGER]
