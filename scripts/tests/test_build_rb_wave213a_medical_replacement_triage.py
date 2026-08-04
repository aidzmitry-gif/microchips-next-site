import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "docs/audits/generated/wave213a-medical-replacement-triage.csv"
SUMMARY_PATH = ROOT / "docs/audits/generated/wave213a-medical-replacement-triage.summary.json"
LIVE_PATH = ROOT / "docs/audits/generated/wave213a-medical-replacement-live-identity-collisions.json"
APPLY0_PATH = ROOT / "docs/audits/generated/wave213a-medical-replacement-laravel-apply0.json"
MANIFEST_PATH = ROOT / "docs/imports/rb-verified-oem-identities-wave213a-medical-2026-07-29.json"


def rows():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_exact_medical_b2b_union_and_extracted_identity_fields():
    data = rows()
    assert len(data) == len({row["product_external_id"] for row in data}) == 274
    assert {row["category_external_id"] for row in data} == {"seo:replacement-medical"}
    assert all(row["device_oem"] and row["device_model"] and row["device_family"] for row in data)
    assert all(row["capacity_mah"] for row in data)
    assert all(row["safe_to_apply"] == "false" for row in data)
    assert Counter(row["source_route"] for row in data)


def test_variant_registry_and_live_db_guards_are_explicit_and_read_only():
    data = rows()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    live = json.loads(LIVE_PATH.read_text(encoding="utf-8"))
    apply0 = json.loads(APPLY0_PATH.read_text(encoding="utf-8"))
    assert any(int(row["in_wave_variant_group_size"]) > 1 for row in data)
    assert summary["processed_register"]["overlap_rows"] == 0
    assert summary["target"]["medical_b2b_rows"] == 274
    assert summary["database_queries"] == 1
    assert summary["database_mutations"] == summary["safe_to_apply_records"] == 0
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 274
    assert live["database_mutations"] == live["apply_records"] == 0
    assert apply0["records"] == apply0["database_mutations"] == 0


def test_manifest_fails_closed_without_exact_sellable_pack_evidence():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert manifest["products"] == []
