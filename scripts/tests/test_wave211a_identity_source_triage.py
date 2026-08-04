import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/audits/generated/wave211a-identity-source-triage.csv"
SUMMARY = ROOT / "docs/audits/generated/wave211a-identity-source-triage.summary.json"

def rows():
    with CSV.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))

def test_union_scope_and_fail_closed_policy():
    data = rows()
    assert len(data) == len({r["product_external_id"] for r in data}) == 213
    assert Counter(r["manufacturer_cluster"] for r in data) == Counter({"unresolved_replacement": 104, "unresolved_other": 23, "unresolved_industrial_cell": 23, "Восток": 17, "General Security": 29, "Security Force": 8, "Alarm Force": 3, "Optimus": 6})
    assert sum(r["scope"] == "medical_specialist_source_required" for r in data) == 104
    assert {r["route_partition"] for r in data} == {"hold"}
    assert {r["safe_to_apply"] for r in data} == {"false"}

def test_no_repeat_exclusions_and_db0_are_explicit():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["processed_register"]["rows"] == 1500
    assert summary["processed_register"]["overlap_rows"] == 0
    assert summary["scope_routes"]["automotive_rows"] == summary["scope_routes"]["electronics_rows"] == 0
    assert summary["scope_routes"]["medical_specialist_rows"] == 104
    assert summary["automatic_web_requests"] == summary["automatic_database_queries"] == summary["automatic_database_mutations"] == 0
    assert summary["live_db"]["status"] == "not_checked_db0"

def test_identity_and_registry_evidence_are_not_fabricated():
    data = rows()
    assert all(r["product_pack_form"] == "" or r["product_pack_form"] in r["name"] for r in data)
    assert all(r["live_db_collision_status"] == "not_checked_db0" for r in data)
    assert all(r["hold_reason"] and "safe_to_apply=false" not in r["hold_reason"] for r in data)
