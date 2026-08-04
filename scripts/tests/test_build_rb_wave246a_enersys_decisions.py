import csv, hashlib, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(path):return json.loads((ROOT/path).read_text(encoding="utf-8"))

def test_wave246a_enersys_is_exact_complete_no_repeat_and_fail_closed():
 p=subprocess.run([sys.executable,str(ROOT/"scripts/build-rb-wave246a-enersys-decisions.py")],cwd=ROOT,capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 summary=load("docs/audits/generated/rb-wave246a-enersys.summary.json")
 assert summary["scope"]=={"rows":92,"series":{"Cyclon":15,"DataSafe HX":17,"PowerSafe V-FT":9,"PowerSafe SBS":32,"PowerSafe RH":19}}
 assert summary["no_repeat"]=={"prior_identity_covered":92,"prior_description_covered":92,"new_identity_manifest_rows":0,"new_description_manifest_rows":0}
 assert summary["sources"]=={"reused":5,"new":1,"redownloaded_family_sources":0}
 assert summary["live"]=={"unique_exact_owner":92,"one_c_owner_conflicts":0}
 assert summary["decisions"]=={"PASS":0,"HOLD":92,"media_hold":92,"duplicate_pass":92}
 assert summary["database_operations"]==0
 with (ROOT/"docs/audits/generated/rb-wave246a-enersys-decision-ledger.csv").open(encoding="utf-8-sig",newline="") as h: rows=list(csv.DictReader(h))
 assert len(rows)==92 and [int(r["scope_order"]) for r in rows]==list(range(1,93))
 assert all(r["identity_action"]==r["description_action"]=="SKIP_ALREADY_APPLIED" for r in rows)
 assert all(r["live_exact_owner_count"]=="1" and r["live_1c_owner_count"]=="0" for r in rows)
 assert all(r["duplicate_decision"]=="PASS_UNIQUE_EXACT_OWNER" and r["final_decision"]=="HOLD" for r in rows)
 assert all("ENERSYS_TERMS_NO_COMMERCIAL_IMAGE_REUSE_WITHOUT_PERMISSION" in r["hold_reason"] for r in rows)
 for short,long in [("12V100F","12V100FC"),("SBS 30","SBS 300"),("SBS 100","SBS 100F")]:
  row=next(r for r in rows if r["mpn"]==short); assert long not in row["live_exact_owner_external_ids"]
 actions=load("docs/audits/generated/rb-wave246a-enersys-manifest-actions.json")
 assert actions["identity_manifest_created"] is False and actions["description_manifest_created"] is False
 assert actions["laravel_validation"]["temporary_description_subset_rows"]==92
 media=load("docs/audits/generated/rb-wave246a-enersys-media-decisions.json")["decisions"]
 assert len(media)==92 and all(r["decision"]=="HOLD" and not r["promotion_allowed"] for r in media)
 terms=load("docs/audits/sources/wave246a-enersys/terms-registry.json")
 assert hashlib.sha256((ROOT/terms["local_path"]).read_bytes()).hexdigest()==terms["sha256"]
 sources=load("docs/audits/sources/wave246a-enersys/reuse-registry.json")["sources"]
 assert len(sources)==6 and sum(r["reuse_status"]=="REUSED_NO_REDOWNLOAD" for r in sources)==5
