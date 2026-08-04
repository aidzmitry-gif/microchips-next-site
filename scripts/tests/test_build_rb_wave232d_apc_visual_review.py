import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/imports/rb-apc-visual-review-wave232d-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave232d-apc-visual-review.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232d-apc-visual-review.summary.json"


def test_wave232d_reviews_exactly_28_apc_assets_and_has_no_promotion_scope():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == {"schema_version", "locale", "reviewed_images", "promotion_candidates", "policy"}
    assert manifest["locale"] == "ru-BY"
    assert len(manifest["reviewed_images"]) == 28
    assert len({row["external_id"] for row in manifest["reviewed_images"]}) == 28
    assert manifest["promotion_candidates"] == []
    assert all(row["official_source_url"].startswith("https://www.se.com/") for row in manifest["reviewed_images"])
    assert all(row["official_identity_status"] == "exact_model_proven" for row in manifest["reviewed_images"])
    assert all(row["ocr_verdict"] == row["visual_verdict"] == "HOLD" for row in manifest["reviewed_images"])
    assert all(row["disposition"] == "HOLD_exact_mpn_not_visibly_legible_or_generic_asset" for row in manifest["reviewed_images"])


def test_wave232d_ledger_and_summary_are_fail_closed_and_rights_limited():
    with LEDGER.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 28
    assert all(row["rights_basis"] == "Company-owned Microchips legacy Bitrix upload backup." for row in rows)
    assert all("generic appearance is insufficient" in row["visual_verification_note"] for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert {key: summary[key] for key in ("candidate_rows", "official_exact_identity_proven", "company_owned_media_hash_pinned", "ocr_hold", "visual_hold", "pass", "promotion_candidates")} == {
        "candidate_rows": 28, "official_exact_identity_proven": 28, "company_owned_media_hash_pinned": 28,
        "ocr_hold": 28, "visual_hold": 28, "pass": 0, "promotion_candidates": 0,
    }
    assert summary["safety"]["image_copying_from_official_sources"] == 0
    assert summary["safety"]["import_or_promotion_manifest_for_command"] is False
