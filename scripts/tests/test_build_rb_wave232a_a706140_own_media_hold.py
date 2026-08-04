import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/audits/generated/rb-wave232a-a706140-own-media-search.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave232a-a706140-own-media-search.summary.json"


def test_wave232a_records_a_fail_closed_hold_not_an_import_or_promotion_manifest():
    with LEDGER.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["product_external_id"] == "bitrix:2808"
    assert row["expected_mpn"] == "A706/140"
    assert row["own_media_search_result"] == "HOLD_no_exact_company_owned_asset_found"
    assert row["visible_label"] == "A706/105"
    assert row["duplicate_bitrix_element_id"] == "28844"
    assert row["duplicate_asset_available"] == "false"
    assert row["official_candidate_source_url"] == "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A700_en.pdf"
    assert "no image reuse licence" in row["rights_status"]


def test_wave232a_summary_forbids_media_mutation_until_a_rights_cleared_exact_asset_exists():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["result"] == "HOLD_no_exact_company_owned_asset_found"
    assert summary["local_search"]["exact_matches"] == 0
    assert summary["local_search"]["duplicate_assets_available"] == 0
    assert summary["official_candidate"]["model_token"] == "A706/140"
    assert summary["safety"] == {
        "media_import_manifest_created": False,
        "media_promotion_manifest_created": False,
        "database_operations": 0,
        "apply_performed": False,
        "commit_or_push": False,
    }
