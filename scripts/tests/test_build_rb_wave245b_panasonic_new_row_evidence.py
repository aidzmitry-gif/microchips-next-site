import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/audits/generated/rb-wave245b-panasonic-new-row-ledger.csv"
IMAGES = ROOT / "docs/audits/generated/rb-wave245b-panasonic-image-candidates.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave245b-panasonic-new-row.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave245b-panasonic-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave245b-panasonic-2026-07-30.json"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave245b_builder_is_reproducible_and_fail_closed():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave245b-panasonic-new-row-evidence.py")], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    ledger = {row["external_id"]: row for row in rows(LEDGER)}
    assert set(ledger) == {"bitrix:1596", "bitrix:1159"}
    assert ledger["bitrix:1596"]["decision"] == "PASS_DESCRIPTION_IDENTITY"
    assert ledger["bitrix:1159"]["decision"] == "HOLD"
    assert ledger["bitrix:1159"]["hold_reason"] == "NO_NEW_EXACT_MANUFACTURER_PRIMARY_SOURCE"
    assert all(row["ownership_decision"] == "NO_EXACT_1C_OWNER" for row in ledger.values())


def test_only_pass_row_enters_non_media_manifests():
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert [row["external_id"] for row in identities] == ["bitrix:1596"]
    assert [row["external_id"] for row in descriptions] == ["bitrix:1596"]
    assert identities[0]["manufacturer"] == "Panasonic"
    assert identities[0]["mpn"] == "LC-XC1238P"
    assert identities[0]["product_type"] == "VRLA AGM battery"
    assert identities[0]["source_kind"] == "official_manufacturer_catalogue"
    assert identities[0]["checked_at"] == "2026-07-29"
    assert descriptions[0]["source_kind"] == "official_manufacturer_catalogue"
    assert descriptions[0]["identity_scope"] == "model_core"
    assert descriptions[0]["evidence_scope"] == "model_core"
    assert descriptions[0]["checked_at"] == "2026-07-29"
    assert descriptions[0]["technical_attributes"]["Номинальная ёмкость (20-часовой режим), А·ч"] == "38.0"


def test_image_candidate_is_local_exact_visually_reviewed_and_rights_hold():
    images = {row["external_id"]: row for row in rows(IMAGES)}
    candidate = images["bitrix:1596"]
    path = ROOT / candidate["candidate_path"]
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == candidate["candidate_sha256"]
    assert candidate["candidate_dimensions_px"] == "203x205"
    assert candidate["visual_review"] == "PASS_EXACT_MODEL_PAGE_PHOTO"
    assert candidate["rights_status"] == "HOLD_NO_EXPLICIT_REUSE_LICENSE"
    assert candidate["media_manifest_eligible"] == "false"
    assert images["bitrix:1159"]["official_exact_image_candidate"] == "false"
    assert not list((ROOT / "docs/imports").glob("*wave245b*media*.json"))


def test_summary_records_zero_overlap_zero_apply_and_bounded_hold():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["scope"] == ["bitrix:1596", "bitrix:1159"]
    assert summary["new_source_safety"]["prior_url_overlap"] == 0
    assert summary["new_source_safety"]["prior_sha_overlap"] == 0
    assert summary["bounded_xd1217_discovery"] == {"candidate_urls": 96, "exact_matches": 0}
    assert summary["manifests"] == {"identities": 1, "descriptions": 1, "media": 0}
    assert summary["safety"]["apply_performed"] is False
    assert summary["safety"]["database_mutations"] == 0
