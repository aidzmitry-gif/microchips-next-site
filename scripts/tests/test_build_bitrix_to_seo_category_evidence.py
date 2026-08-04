import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-bitrix-to-seo-category-evidence.py"
SPEC = importlib.util.spec_from_file_location("bitrix_category_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_focus_manifest_is_complete_and_never_releases_categories():
    categories = [
        {"external_id": "1", "parent_external_id": "", "name": "UPS", "path": "catalog/batteries/ups"},
        {"external_id": "2", "parent_external_id": "", "name": "UPS", "path": "catalog/batteries/ups9002"},
        {"external_id": "3", "parent_external_id": "", "name": "AGM", "path": "catalog/batteries/agm"},
        {"external_id": "4", "parent_external_id": "", "name": "Outside focus", "path": "catalog/other"},
    ]
    records = [
        record("10", "batteries/agm", "strict_mapped_evidence", "P1", ["seo:batteries-ups"]),
        record("11", "batteries/agm", "strict_mapped_evidence", "P2", ["seo:batteries-ups"]),
        record("12", "batteries/agm", "strict_mapped_evidence", "P3", ["seo:batteries-ups"]),
        record("13", "batteries/ups", "hold_missing_1c_identity", "", []),
    ]

    rows, summary = MODULE.build(categories, records, {})
    by_path = {row["legacy_path"]: row for row in rows}

    assert by_path["batteries/ups"]["preview_decision"] == "focus_populated"
    assert by_path["batteries/ups9002"]["preview_decision"] == "empty_duplicate_candidate"
    assert by_path["batteries/ups9002"]["canonical_category_external_id"] == "1"
    assert by_path["batteries/agm"]["preliminary_seo_target"] == "seo:batteries-ups"
    assert by_path["other"]["preview_decision"] == "empty_in_focus_preview"
    assert all(row["release_allowed"] == "false" for row in rows)
    assert summary["release_allowed_rows"] == 0


def test_override_replaces_stale_non_seo_category_vote():
    categories = [{"external_id": "1", "parent_external_id": "", "name": "AGM", "path": "catalog/agm"}]
    records = [record(str(index), "agm", "strict_mapped_evidence", f"P{index}", ["410"]) for index in range(1, 4)]

    rows, _ = MODULE.build(
        categories,
        records,
        {f"P{index}": {"seo:batteries-ups"} for index in range(1, 4)},
    )

    assert rows[0]["preliminary_seo_target"] == "seo:batteries-ups"
    assert rows[0]["strict_product_count"] == "3"


def record(legacy_id, path, status, one_c, categories):
    return {
        "legacy_element_id": legacy_id,
        "legacy_primary_section_path": path,
        "legacy_matched_section_paths": path,
        "transfer_status": status,
        "one_c_external_id": one_c,
        "rb_category_external_ids": categories,
    }
