import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];GEN=ROOT/"docs/audits/generated"
def rows(p):
 with p.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def test_wave219a_scope_type_and_fail_closed_identity():
 e=rows(GEN/"rb-wave219a-final-remainder-evidence.csv");s=json.loads((GEN/"rb-wave219a-final-remainder.summary.json").read_text(encoding="utf-8"))
 assert len(e)==len({r["product_external_id"] for r in e})==277
 assert Counter(r["source_cluster"] for r in e)=={"unresolved_other":269,"unresolved_industrial_cell":7,"unresolved_replacement":1}
 assert all(r["safe_to_apply"]=="false" and r["bounded_model_token"] and r["family_group"] for r in e)
 assert s["scope"]=={"processed_overlap_ids":[],"prior_evidence_overlap_ids":[],"automotive_rows":0,"electronics_component_rows":0}
def test_wave219a_guards_and_conservative_taxonomy_dry_runs():
 s=json.loads((GEN/"rb-wave219a-final-remainder.summary.json").read_text(encoding="utf-8"));d=json.loads((GEN/"wave219a-final-remainder-laravel-dry-run.json").read_text(encoding="utf-8"));t=json.loads((GEN/"wave219a-taxonomy-laravel-dry-run.json").read_text(encoding="utf-8"));m=rows(ROOT/"docs/imports/rb-site-category-move-wave219a-obvious-power-supplies.csv")
 assert d["exit_code"]!=0 and d["apply_flag_used"] is False and d["database_mutations"]==0
 assert len(m)==6 and all(r["from_category_external_id"]=="seo:chargers" and r["to_category_external_id"]=="seo:power-supplies" for r in m)
 assert t["exit_code"]==0 and t["apply_flag_used"] is False and t["category_link_mutations"]==t["url_mutations"]==t["canonical_mutations"]==0
 assert s["live_collision_guard"]["database_mutations"]==0 and s["policy"]["database_apply"] is False
