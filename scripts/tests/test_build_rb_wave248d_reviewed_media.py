import csv
import json
from pathlib import Path


ROOT = Path.cwd()
MANIFEST = ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave248d-2026-07-30.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave248d-reviewed-media-2026-07-30.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave248d-reviewed-media-2026-07-30.json"


def test_wave248d_promotion_scope_is_exactly_two_visible_yuasa_models():
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert payload["locale"] == "ru-BY"
    assert {row["external_id"] for row in payload["images"]} == {"bitrix:24373", "bitrix:24374"}
    assert {row["mpn"] for row in payload["images"]} == {"DCB145-6", "DCB105-6"}
    assert all(row["identity_evidence_level"] == "visible_exact_mpn" for row in payload["images"])
    assert all("company-owned" in row["rights_basis"].casefold() for row in payload["images"])


def test_wave248d_ledger_is_complete_and_fail_closed():
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 34
    assert sum(row["visual_verdict"] == "PASS" for row in rows) == 2
    assert sum(row["visual_verdict"] == "HOLD" for row in rows) == 32
    assert sum(row["disposition"] == "shared_asset_hash_across_products" for row in rows) == 28
    assert all(row["visual_verdict"] == "HOLD" for row in rows if row["external_id"] in {"bitrix:20397", "bitrix:25120", "bitrix:25135", "bitrix:25149"})


def test_wave248d_summary_records_no_implicit_apply():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert {key: summary[key] for key in ("reviewed", "shared_hash_holds", "selected_visual_reviews", "pass", "hold")} == {
        "reviewed": 34,
        "shared_hash_holds": 28,
        "selected_visual_reviews": 6,
        "pass": 2,
        "hold": 32,
    }
    assert summary["database_apply"] is False
    assert summary["publication_changes"] == 0
