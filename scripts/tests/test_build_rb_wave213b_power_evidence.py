import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave212.csv"
EVIDENCE = GEN / "rb-wave213b-power-evidence.csv"
SUMMARY = GEN / "rb-wave213b-power-evidence.summary.json"
LIVE = GEN / "wave213b-power-live-identity-collisions.json"
DRY = GEN / "wave213b-power-laravel-dry-run.json"
SOURCES = ROOT / "docs/audits/sources/wave213b-power/source-registry.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave213b-power-2026-07-29.json"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave213b_is_exact_221_power_system_union_without_category_leakage():
    source = [row for row in rows(INPUT) if row["manufacturer_cluster"] == "unresolved_other" and row["category_external_id"] == "seo:power-systems"]
    evidence = rows(EVIDENCE)
    assert len(source) == len(evidence) == 221
    assert {row["product_external_id"] for row in source} == {row["product_external_id"] for row in evidence}
    assert all(row["factual_type"] == "power_system_ac_dc_power_supply" for row in evidence)
    assert all(row["factual_type"] not in {"UPS", "inverter", "battery", "accessory", "electronics_component"} for row in evidence)
    assert all(row["model_candidate"] and row["family_group"] and row["variant_group"] and row["duplicate_group"] for row in evidence)


def test_wave213b_is_fail_closed_for_lookalike_and_unbranded_models():
    evidence = rows(EVIDENCE)
    parts = Counter(row["partition"] for row in evidence)
    assert parts == {"manufacturer_hold": 207, "exact_safe": 13, "conflict": 1}
    zgqnyi = [row for row in evidence if row["manufacturer"] == "ZGQNYI"]
    assert len(zgqnyi) == 164
    assert all(row["safe_to_apply"] == "false" for row in zgqnyi)
    assert all("Mean_Well_like_series_name" in row["conflict_reason"] for row in zgqnyi)
    irm = next(row for row in evidence if row["product_external_id"] == "bitrix:20429")
    assert irm["partition"] == "conflict"
    assert "lacks_bounded_manufacturer" in irm["conflict_reason"]


def test_wave213b_pins_primary_sources_and_manifest_is_exact_safe_subset():
    source_registry = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    assert len(source_registry) == 5
    for source in source_registry:
        snapshot = ROOT / source["snapshot_path"]
        assert urlparse(source["source_url"]).scheme == "https"
        assert urlparse(source["source_url"]).hostname == "www.meanwell.com"
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
    evidence = rows(EVIDENCE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    safe_ids = {row["product_external_id"] for row in evidence if row["safe_to_apply"] == "true"}
    assert len(safe_ids) == 13
    assert {row["external_id"] for row in manifest["products"]} == safe_ids
    assert all(row["manufacturer"] == "Mean Well" and "Mean Well" in row["current_name"] for row in manifest["products"])
    assert all(row["source_kind"] == "official_manufacturer_catalogue" for row in manifest["products"])


def test_wave213b_full_registry_live_guard_and_dry_run_are_zero_apply():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    assert summary["input"]["rows"] == 221
    assert summary["scope"] == {"unresolved_other_power_system_rows": 221, "ups_rows": 0, "inverter_rows": 0, "battery_rows": 0, "accessory_rows": 0, "electronics_component_rows": 0, "processed2000_overlap_ids": []}
    assert summary["canonical_registry"]["collision_rows"] == 0
    assert live["mode"] == "read_only" and live["query_exit_code"] == 0
    assert live["candidate_rows_checked"] == 221 and all(not row["conflicting_external_ids"] for row in live["checks"])
    assert dry["mode"] == "dry_run" and dry["exit_code"] == 0 and dry["apply_flag_used"] is False
    assert dry["records"] == 13 and dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["database_mutations"] == dry["commercial_fields_changed"] == dry["publication_fields_changed"] == 0
