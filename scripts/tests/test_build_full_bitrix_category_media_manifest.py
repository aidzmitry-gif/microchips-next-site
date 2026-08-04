import csv
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-full-bitrix-category-media-manifest.py"
SPEC = importlib.util.spec_from_file_location("full_bitrix_category_media", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_index(path: Path) -> None:
    rows = [
        {"legacy_element_id": "10", "active": "Y", "name": "A", "preview_picture_file_id": "100", "detail_picture_file_id": "101"},
        {"legacy_element_id": "11", "active": "Y", "name": "B", "preview_picture_file_id": "", "detail_picture_file_id": ""},
        {"legacy_element_id": "12", "active": "Y", "name": "C", "preview_picture_file_id": "120", "detail_picture_file_id": ""},
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_builds_only_safe_same_element_preview_rows(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    staging.write_text(json.dumps({"records": [
        {"bitrix_id": "10", "name": "A", "target_category_external_id": "seo:primary-cells", "transfer_status": "legacy_only_draft_candidate"},
        {"bitrix_id": "11", "name": "B", "target_category_external_id": "seo:primary-cells", "transfer_status": "legacy_only_draft_candidate"},
        {"bitrix_id": "12", "name": "C", "target_category_external_id": "seo:primary-cells", "transfer_status": "hold_duplicate_candidate"},
        {"bitrix_id": "13", "name": "D", "target_category_external_id": "seo:primary-cells", "transfer_status": "legacy_only_draft_candidate"},
        {"bitrix_id": "14", "name": "Other", "target_category_external_id": "seo:chargers", "transfer_status": "legacy_only_draft_candidate"},
    ]}), encoding="utf-8")
    index = tmp_path / "index.csv"
    write_index(index)
    output = tmp_path / "manifest.json"

    summary = MODULE.build(staging, index, "seo:primary-cells", output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert [row["legacy_element_id"] for row in payload["records"]] == ["10"]
    assert summary["scoped_staging_records"] == 4
    assert summary["safe_legacy_drafts"] == 3
    assert summary["records_with_media_reference"] == 1
    assert summary["unique_selected_file_references"] == 1
    assert summary["safe_drafts_without_media_reference"] == 1
    assert summary["safe_drafts_missing_media_index"] == 1
    assert summary["canonical_one_c_media_imports"] == 0
    assert output.with_suffix(".file-ids.txt").read_text(encoding="utf-8") == "101\n"


def test_combines_multiple_categories_without_relaxing_transfer_gate(tmp_path: Path) -> None:
    staging = tmp_path / "staging.json"
    staging.write_text(json.dumps({"records": [
        {"bitrix_id": "10", "name": "A", "target_category_external_id": "seo:primary-cells", "transfer_status": "legacy_only_draft_candidate"},
        {"bitrix_id": "12", "name": "C", "target_category_external_id": "seo:chargers", "transfer_status": "legacy_only_draft_candidate"},
        {"bitrix_id": "11", "name": "B", "target_category_external_id": "seo:chargers", "transfer_status": "hold_duplicate_candidate"},
    ]}), encoding="utf-8")
    index = tmp_path / "index.csv"
    write_index(index)
    output = tmp_path / "manifest.json"

    summary = MODULE.build(staging, index, ["seo:primary-cells", "seo:chargers"], output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert [row["legacy_element_id"] for row in payload["records"]] == ["10", "12"]
    assert summary["categories"] == ["seo:primary-cells", "seo:chargers"]
    assert summary["category_record_counts"] == {"seo:chargers": 2, "seo:primary-cells": 1}
    assert summary["transfer_statuses"] == {"hold_duplicate_candidate": 1, "legacy_only_draft_candidate": 2}
