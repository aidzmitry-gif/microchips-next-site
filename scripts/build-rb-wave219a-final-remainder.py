#!/usr/bin/env python3
"""Fail-closed Wave219-A final research remainder and taxonomy candidates."""
from __future__ import annotations
import base64,csv,hashlib,importlib.util,json,re,subprocess
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/"docs/audits/generated"
INPUT=GEN/"rb-b2b-next-source-batch-wave218.csv"; PROCESSED=GEN/"rb-b2b-processed-register-wave218.csv"; REGISTRY=GEN/"full-catalog-canonical-registry.csv"
OUT=GEN/"rb-wave219a-final-remainder-evidence.csv"; SUM=GEN/"rb-wave219a-final-remainder.summary.json"; LIVE=GEN/"wave219a-final-remainder-live-collisions.json"; DRY=GEN/"wave219a-final-remainder-laravel-dry-run.json"
MANIFEST=ROOT/"docs/imports/rb-verified-oem-identities-wave219a-final-remainder-2026-07-29.json"; TAX=GEN/"rb-wave219a-taxonomy-candidates.csv"; TAXMAN=ROOT/"docs/imports/rb-site-category-move-wave219a-obvious-power-supplies.csv"; TAXDRY=GEN/"wave219a-taxonomy-laravel-dry-run.json"; REPORT=ROOT/"docs/audits/2026-07-29-rb-wave219a-final-remainder.md"
PIN="c39570a34f469c22bc55c3b66091440ed48e406f399f672a722854f188438545"
FIELDS=["batch","product_external_id","name","category_external_id","source_cluster","factual_product_type","manufacturer_candidate","manufacturer_status","model_candidate","bounded_model_token","family_group","primary_manufacturer_source_route","partition","conflict_reason","registry_exact_title_duplicates","registry_model_candidate_external_ids","live_db_collision_external_ids","safe_to_apply"]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def helper():
 s=importlib.util.spec_from_file_location("w217",ROOT/"scripts/build-rb-wave217a-unresolved-evidence.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def typ(r):
 n,c=r["name"],r["category_external_id"]
 if c=="seo:replacement-tools": return "power_tool_battery_charger_kit" if re.search(r"с зарядным устройством",n,re.I) else "power_tool_replacement_battery"
 if c=="seo:chargers": return "power_supply_adapter" if n.casefold().startswith("блок питания") else "battery_charger"
 if c=="seo:batteries-traction": return "traction_battery"
 if c=="seo:power-supplies": return "ac_dc_power_supply"
 if c=="seo:power-converters": return "dc_dc_power_converter"
 if c=="seo:ups-systems": return "ups_system"
 raise ValueError(n)
def live():
 php="echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);";q=base64.b64encode(php.encode()).decode();r=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","tinker",f"--execute=eval(base64_decode('{q}'));"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
 if r.returncode or not r.stdout.strip().startswith("["):raise SystemExit(r.stderr or r.stdout)
 return json.loads(r.stdout)
def main():
 h=helper(); src=rows(INPUT); sel=[r for r in src if r["manufacturer_cluster"] in {"unresolved_other","unresolved_industrial_cell","unresolved_replacement"}]; ids=[r["product_external_id"] for r in sel]
 if sha(INPUT)!=PIN or len(sel)!=277 or len(ids)!=len(set(ids)) or Counter(r["manufacturer_cluster"] for r in sel)!={"unresolved_other":269,"unresolved_industrial_cell":7,"unresolved_replacement":1}:raise SystemExit("scope drift")
 if any(h.AUTOMOTIVE.search(r["name"]) or h.ELECTRONICS.search(r["name"]) for r in sel):raise SystemExit("scope leak")
 done={r["product_external_id"] for r in rows(PROCESSED)}
 if set(ids)&done:raise SystemExit("processed overlap")
 prior={r.get("product_external_id","") for p in GEN.glob("rb-wave*-evidence.csv") if p.name!=OUT.name for r in rows(p)}
 if set(ids)&prior:raise SystemExit("prior evidence overlap")
 reg=rows(REGISTRY); titles=defaultdict(list); names=[]
 for r in reg: titles[h.norm(r["name"])].append(r["registry_id"]);names.append((r["registry_id"],h.norm(r["name"])))
 products=live();byid={r["external_id"]:r for r in products}
 if set(ids)-set(byid):raise SystemExit("missing live product")
 li=defaultdict(list)
 for r in products:
  for v in (r.get("sku_normalized") or r.get("sku") or "",r.get("mpn_normalized") or r.get("mpn") or ""):
   if (k:=h.norm(str(v))):li[k].append(r["external_id"])
 ev=[];checks=[];tax=[]
 for r in sel:
  pt=typ(r);brand,model,token,fam=h.identity(r["name"]);k=h.norm(token);eid=r["product_external_id"]
  td=sorted(x for x in titles[h.norm(r["name"])] if x!=eid);rp=sorted({x for x,n in names if x!=eid and k and k in n});lp=sorted(x for x in li.get(k,[]) if x!=eid)
  reason="exact_current_ID_title_bounded_model_manufacturer_primary_source_required" if brand else "manufacturer_unresolved; primary source required"
  ev.append({"batch":"wave219a_final_remainder","product_external_id":eid,"name":r["name"],"category_external_id":r["category_external_id"],"source_cluster":r["manufacturer_cluster"],"factual_product_type":pt,"manufacturer_candidate":brand,"manufacturer_status":"title_label_candidate" if brand else "manufacturer_unresolved","model_candidate":model,"bounded_model_token":token,"family_group":fam,"primary_manufacturer_source_route":f"{brand or 'manufacturer_resolution'}_first_party_{pt}_source_required","partition":"primary_source_batch_hold","conflict_reason":reason,"registry_exact_title_duplicates":"|".join(td),"registry_model_candidate_external_ids":"|".join(rp),"live_db_collision_external_ids":"|".join(lp),"safe_to_apply":"false"});checks.append({"candidate_external_id":eid,"bounded_model_token_normalized":k,"conflicting_external_ids":lp})
  if pt=="power_supply_adapter":tax.append({"product_external_id":eid,"from_category_external_id":"seo:chargers","to_category_external_id":"seo:power-supplies","name":r["name"],"reason":"explicit power supply title, not charger"})
 if len(tax)!=6 or any(x["from_category_external_id"]==x["to_category_external_id"] for x in tax):raise SystemExit("taxonomy candidate drift")
 with OUT.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=FIELDS,lineterminator="\n");w.writeheader();w.writerows(ev)
 for p,data,fs in ((MANIFEST,{"schema_version":1,"site_key":"microchips-by","products":[]},None),(TAX,None,["product_external_id","from_category_external_id","to_category_external_id","name","reason"]),(TAXMAN,None,["product_external_id","from_category_external_id","to_category_external_id"])):
  if data is not None:p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  else:
   with p.open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=fs,lineterminator="\n");w.writeheader();w.writerows(({z:x[z] for z in fs} for x in tax))
 def cp(p):
  q="/tmp/"+p.name;r=subprocess.run(["docker","compose","cp",str(p),"backend:"+q],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
  if r.returncode:raise SystemExit(r.stderr or r.stdout)
  return q
 q=cp(MANIFEST);r=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","catalog:apply-verified-oem-identities","microchips-by",q],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
 if r.returncode==0 or "non-empty products list" not in r.stdout+r.stderr:raise SystemExit("identity dry run did not fail closed")
 dry={"mode":"dry_run","apply_flag_used":False,"exit_code":r.returncode,"records":0,"manifest_sha256":sha(MANIFEST),"stdout":r.stdout.strip(),"stderr":r.stderr.strip(),"database_mutations":0};DRY.write_text(json.dumps(dry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 q=cp(TAXMAN);r=subprocess.run(["docker","compose","exec","-T","backend","php","artisan","catalog:move-site-product-categories","microchips-by",q,"--category-source=full_catalog_seo_tree"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
 if r.returncode:raise SystemExit(r.stderr or r.stdout)
 taxdry={"mode":"dry_run","apply_flag_used":False,"exit_code":0,"records":6,"manifest_sha256":sha(TAXMAN),"stdout":r.stdout.strip(),"stderr":r.stderr.strip(),"category_link_mutations":0,"url_mutations":0,"canonical_mutations":0};TAXDRY.write_text(json.dumps(taxdry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 LIVE.write_text(json.dumps({"schema_version":1,"mode":"read_only","database_mutations":0,"candidate_rows_checked":277,"checks":checks},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 summary={"schema_version":1,"batch":"wave219a_final_remainder","input":{"path":INPUT.relative_to(ROOT).as_posix(),"sha256":sha(INPUT),"rows":277,"cluster_counts":dict(sorted(Counter(r["source_cluster"] for r in ev).items()))},"scope":{"processed_overlap_ids":[],"prior_evidence_overlap_ids":[],"automotive_rows":0,"electronics_component_rows":0},"product_type_counts":dict(sorted(Counter(r["factual_product_type"] for r in ev).items())),"partition_counts":{"primary_source_batch_hold":277},"taxonomy_candidates":{"rows":6,"to_power_supplies":6,"dry_run_exit":0,"apply_flag_used":False},"canonical_registry":{"path":REGISTRY.relative_to(ROOT).as_posix(),"sha256":sha(REGISTRY),"rows":len(reg),"exact_title_collision_rows":sum(bool(r["registry_exact_title_duplicates"]) for r in ev),"model_candidate_collision_rows":sum(bool(r["registry_model_candidate_external_ids"]) for r in ev)},"live_collision_guard":{"rows":277,"collision_rows":sum(bool(r["live_db_collision_external_ids"]) for r in ev),"database_mutations":0},"manifest":{"rows":0,"sha256":sha(MANIFEST)},"laravel_dry_run":{"exit_code":dry["exit_code"],"database_mutations":0},"policy":{"title_or_compatibility_not_identity":True,"database_apply":False}}
 SUM.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 REPORT.write_text("# Wave219-A final research remainder\n\nClassified exactly 277 final unresolved research rows; every identity remains a primary-source hold and the exact-safe OEM manifest is empty.\n\n- Clusters: "+str(summary["input"]["cluster_counts"])+"\n- Product types: "+str(summary["product_type_counts"])+"\n- No automotive/electronic rows and no processed/prior-evidence overlap.\n- Six explicit `Блок питания` rows in `seo:chargers` are taxonomy candidates for `seo:power-supplies`; mover dry-run passed without `--apply`.\n- Tool compatibility/brand names are not promoted to identity.\n",encoding="utf-8")
 print(json.dumps({"rows":277,"taxonomy_candidates":6,"database_mutations":0}))
if __name__=="__main__":main()
