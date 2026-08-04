import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/imports/rb-legacy-exact-preview-media-wave231c-2026-07-29.json"
AUDIT = ROOT / "docs/audits/generated/rb-wave231a-media-mpn-audit.csv"
CORRECTIONS = ROOT / "docs/imports/rb-truncated-mpn-corrections-wave231b-2026-07-29.json"
ASSET_ROOT = ROOT / ".tmp/wave227-assets"


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def test_wave231c_manifest_matches_exact_promotion_command_schema():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(payload) == {"locale", "images"}
    assert payload["locale"] == "ru-BY"
    assert len(payload["images"]) == 2
    rows = {row["external_id"]: row for row in payload["images"]}
    assert set(rows) == {"bitrix:2831", "bitrix:3117"}
    allowed = {
        "external_id", "media_id", "content_sha256", "storage_path", "rights_basis",
        "identity_scope", "mpn", "identity_evidence_level", "visual_verification_note", "reviewed_at",
    }
    assert rows["bitrix:2831"]["mpn"] == "S 12/17 G5"
    assert rows["bitrix:3117"]["mpn"] == "S 12/6.6 S"
    for row in rows.values():
        assert set(row) == allowed
        assert isinstance(row["media_id"], int) and row["media_id"] > 0
        assert row["identity_scope"] == "exact"
        assert row["identity_evidence_level"] == "visible_exact_mpn"
        assert "model_core" not in row and "manufacturer" not in row
        assert re.fullmatch(r"[a-f0-9]{64}", row["content_sha256"])
        assert row["rights_basis"] == "Company-owned Microchips legacy Bitrix upload backup."
        assert row["reviewed_at"] == "2026-07-29"
        assert normalized(row["mpn"]) in normalized(row["visual_verification_note"])


def test_wave231c_manifest_is_pinned_to_corrected_mpns_audit_media_and_original_assets():
    manifest = {row["external_id"]: row for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["images"]}
    with AUDIT.open(encoding="utf-8-sig", newline="") as handle:
        audit = {row["product_external_id"]: row for row in csv.DictReader(handle)}
    corrected = {row["external_id"]: row for row in json.loads(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]}
    for external_id, row in manifest.items():
        audit_row = audit[external_id]
        correction = corrected[external_id]
        assert audit_row["audit_classification"] == "current_mpn_truncated"
        assert audit_row["apply_status"] == "not_applied"
        assert normalized(audit_row["visible_label"]) == normalized(row["mpn"])
        assert correction["corrected_mpn"] == row["mpn"]
        assert correction["media_id"] == row["media_id"] == int(audit_row["media_id"])
        assert correction["media_content_sha256"] == row["content_sha256"] == audit_row["media_sha256"]
        assert correction["storage_path"] == row["storage_path"] == audit_row["media_storage_key"]
        assert hashlib.sha256((ASSET_ROOT / row["storage_path"]).read_bytes()).hexdigest() == row["content_sha256"]
