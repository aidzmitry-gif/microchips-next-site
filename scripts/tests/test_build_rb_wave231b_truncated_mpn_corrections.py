import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/imports/rb-truncated-mpn-corrections-wave231b-2026-07-29.json"
EXTRACTION = MANIFEST.with_name("rb-truncated-mpn-corrections-wave231b-2026-07-29.extraction.txt")
AUDIT = ROOT / "docs/audits/generated/rb-wave231a-media-mpn-audit.csv"
EXPECTED_NAMES = {
    "bitrix:2831": "Аккумулятор Sonnenschein Dryfit Solar S 12/17 G5 для ИБП (GEL, 17Ah)",
    "bitrix:3117": "Аккумулятор Sonnenschein Dryfit Solar S 12/6.6 S для ИБП (GEL, 6.6Ah)",
}


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def is_cp1251_utf8_mojibake(value: str) -> bool:
    try:
        return value.encode("cp1251").decode("utf-8") != value
    except UnicodeError:
        return False


def test_wave231b_manifest_is_command_shaped_and_pins_only_the_two_truncations():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == {"locale", "corrections"}
    assert manifest["locale"] == "ru-BY"
    assert len(manifest["corrections"]) == 2
    rows = {row["external_id"]: row for row in manifest["corrections"]}
    assert set(rows) == {"bitrix:2831", "bitrix:3117"}
    assert {key: row["current_name"] for key, row in rows.items()} == EXPECTED_NAMES
    assert rows["bitrix:2831"]["corrected_mpn"] == "S 12/17 G5"
    assert rows["bitrix:3117"]["corrected_mpn"] == "S 12/6.6 S"
    allowed = {
        "external_id", "current_name", "manufacturer", "current_mpn", "corrected_mpn",
        "source_url", "source_kind", "source_snapshot_path", "source_snapshot_sha256",
        "source_extraction_path", "source_extraction_sha256", "source_evidence_text",
        "source_evidence_text_sha256", "media_id", "media_content_sha256", "storage_path",
        "rights_basis", "observed_visible_mpn", "checked_at", "review_note",
    }
    extraction = EXTRACTION.read_text(encoding="utf-8")
    for row in rows.values():
        assert set(row) == allowed
        assert not is_cp1251_utf8_mojibake(row["current_name"])
        assert normalized(row["corrected_mpn"]).startswith(normalized(row["current_mpn"]))
        assert normalized(row["observed_visible_mpn"]) == normalized(row["corrected_mpn"])
        assert normalized(row["corrected_mpn"]) in normalized(row["source_evidence_text"])
        assert hashlib.sha256(row["source_evidence_text"].encode()).hexdigest() == row["source_evidence_text_sha256"]
        assert row["source_snapshot_path"] == "exide-sonnenschein-solar-block.pdf"
        assert "/" not in row["source_snapshot_path"] and "\\" not in row["source_snapshot_path"]
        assert row["source_extraction_path"] == EXTRACTION.name
        assert "/" not in row["source_extraction_path"] and "\\" not in row["source_extraction_path"]
        assert hashlib.sha256(EXTRACTION.read_bytes()).hexdigest() == row["source_extraction_sha256"]
        assert normalized(row["source_evidence_text"]) in normalized(extraction)
        assert re.fullmatch(r"[a-f0-9]{64}", row["source_snapshot_sha256"])
        assert re.fullmatch(r"[a-f0-9]{64}", row["source_extraction_sha256"])
        assert re.fullmatch(r"[a-f0-9]{64}", row["media_content_sha256"])


def test_wave231b_manifest_matches_the_not_applied_wave231a_audit_pins():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    with AUDIT.open(encoding="utf-8-sig", newline="") as handle:
        audit = {row["product_external_id"]: row for row in csv.DictReader(handle)}
    for correction in manifest["corrections"]:
        row = audit[correction["external_id"]]
        assert row["audit_classification"] == "current_mpn_truncated"
        assert row["apply_status"] == "not_applied"
        assert correction["current_name"] == row["live_product_name"]
        assert correction["current_name"] == EXPECTED_NAMES[correction["external_id"]]
        assert not is_cp1251_utf8_mojibake(row["live_product_name"])
        assert correction["current_mpn"] == row["current_mpn"]
        assert correction["media_id"] == int(row["media_id"])
        assert correction["media_content_sha256"] == row["media_sha256"]
        assert correction["storage_path"] == row["media_storage_key"]
        assert correction["source_snapshot_sha256"] == row["official_source_sha256"]


def test_wave231b_manifest_is_ascii_serialized_to_prevent_console_codepage_mojibake():
    raw = MANIFEST.read_bytes()
    assert raw.decode("ascii")
    assert b"\\u0410\\u043a" in raw
    assert "Рђ" not in raw.decode("ascii")
