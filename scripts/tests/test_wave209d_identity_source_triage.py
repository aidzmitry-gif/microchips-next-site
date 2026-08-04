import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs/audits/generated/wave209d-identity-source-triage.csv"
SUMMARY = ROOT / "docs/audits/generated/wave209d-identity-source-triage.summary.json"
LIVE = ROOT / "docs/audits/generated/wave209d-live-identity-collisions.json"

def rows():
    with CSV.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))

def test_union_and_safe_hold_policy():
    data = rows()
    assert len(data) == len({r["product_external_id"] for r in data}) == 120
    assert Counter(r["manufacturer_cluster"] for r in data) == Counter({"unresolved_industrial_cell":54,"unresolved_other":33,"unresolved_replacement":1,"Восток":9,"Contact":7,"General Security":8,"Security Force":5,"Alarm Force":2,"Optimus":1})
    assert {r["safe_to_apply"] for r in data} == {"false"}
    assert {r["route_partition"] for r in data} == {"hold"}

def test_a_b_c_are_disjoint_and_collisions_are_recorded():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert all(v["overlap_rows"] == 0 and v["overlap_ids"] == [] for v in summary["wave209_assigned_overlap"].values())
    assert summary["full_registry"]["rows"] > 0
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 120 and live["database_mutations"] == 0

def test_exact_model_and_form_are_not_silently_fabricated():
    data = rows()
    assert any(r["manufacturer_cluster"] == "unresolved_industrial_cell" and r["exact_model_token"] for r in data)
    assert all(r["product_pack_form"] == "" or r["product_pack_form"] in r["name"] for r in data)
    assert all(r["hold_reason"] for r in data)
    assert all("safe_to_apply=false" not in r["hold_reason"] for r in data)
