import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave217a-unresolved-evidence.csv"
SUMMARY = GEN / "rb-wave217a-unresolved-evidence.summary.json"
LIVE = GEN / "wave217a-unresolved-live-identity-collisions.json"
DRY = GEN / "wave217a-unresolved-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave217a-unresolved-2026-07-29.json"

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))

def test_wave217a_exact_scope_product_types_and_no_repeat():
    evidence = rows(EVIDENCE); summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(evidence) == len({row["product_external_id"] for row in evidence}) == 395
    assert Counter(row["category_external_id"] for row in evidence) == {"seo:chargers":172,"seo:replacement-tools":98,"seo:power-systems":84,"seo:warehouse-equipment":39,"seo:batteries-traction":2}
    assert set(row["factual_product_type"] for row in evidence) == {"battery_charger","power_supply_adapter","power_tool_replacement_battery","power_tool_battery_charger_kit","dc_dc_power_converter","laboratory_power_supply","ups_system","manual_pallet_truck","electric_warehouse_stacker","traction_battery"}
    assert all(row["model_candidate"] and row["bounded_model_token"] and row["family_group"] for row in evidence)
    assert summary["scope"] == {"processed3000_overlap_ids":[],"prior_evidence_overlap_ids":[],"automotive_rows":0,"electronics_component_rows":0}

def test_wave217a_primary_source_holds_and_zero_apply_guards():
    evidence = rows(EVIDENCE); summary = json.loads(SUMMARY.read_text(encoding="utf-8")); live = json.loads(LIVE.read_text(encoding="utf-8")); dry = json.loads(DRY.read_text(encoding="utf-8")); manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert Counter(row["partition"] for row in evidence) == {"primary_source_batch_hold":395}
    assert all(row["safe_to_apply"] == "false" and row["source_url"] == "" for row in evidence)
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 395 and live["database_mutations"] == 0
    assert dry["mode"] == "dry_run" and dry["apply_flag_used"] is False and dry["exit_code"] != 0
    assert "non-empty products list" in (dry["stdout"] + dry["stderr"])
    assert manifest["products"] == [] and dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert summary["policy"] == {"exact_primary_source_required":True,"exact_safe_manifest_only":True,"database_apply":False}
