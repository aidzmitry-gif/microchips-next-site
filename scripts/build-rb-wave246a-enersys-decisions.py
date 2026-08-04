#!/usr/bin/env python3
"""Build the deterministic no-repeat Wave246A EnerSys 92-row decision package."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCOPE=ROOT/"docs/audits/generated/rb-wave246-b2b-scope.csv"
LIVE=ROOT/"docs/audits/generated/rb-wave246a-enersys-live-ownership.json"
TERMS=ROOT/"docs/audits/sources/wave246a-enersys/terms-registry.json"
LEDGER=ROOT/"docs/audits/generated/rb-wave246a-enersys-decision-ledger.csv"
SUMMARY=ROOT/"docs/audits/generated/rb-wave246a-enersys.summary.json"
MEDIA=ROOT/"docs/audits/generated/rb-wave246a-enersys-media-decisions.json"
DUPLICATES=ROOT/"docs/audits/generated/rb-wave246a-enersys-duplicate-decisions.json"
ACTIONS=ROOT/"docs/audits/generated/rb-wave246a-enersys-manifest-actions.json"
SOURCES=ROOT/"docs/audits/sources/wave246a-enersys/reuse-registry.json"
REPORT=ROOT/"docs/audits/2026-07-30-rb-wave246a-enersys.md"
PRIOR_VISUAL=ROOT/"docs/audits/generated/rb-wave232e-enersys-cyclon-media-review.csv"

GROUPS={
 "Cyclon":{"count":15,"identity":"docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json","description":"docs/imports/rb-source-backed-descriptions-wave241-2026-07-29.json","source":"docs/audits/sources/wave209a/enersys-cyclon-selection-guide.pdf","url":"https://www.enersys.com/493c0d/globalassets/documents/product-documentation/cyclon/emea/en-cyc-sg-004_0614.pdf"},
 "DataSafe HX":{"count":17,"identity":"docs/imports/rb-manufacturer-product-candidates-enersys-wave179-2026-07-29.json","description":"docs/imports/rb-source-backed-description-drafts-enersys-wave179-2026-07-29.json","source":"docs/imports/rb-manufacturer-series-enersys-wave179-source.json","url":"https://www.enersys.com/49160e/globalassets/documents/product-documentation/datasafe/hx/emea/datasafe_HX_range_summary_emea-en-rs-ds-hx-0223.pdf"},
 "PowerSafe V-FT":{"count":9,"identity":"docs/imports/rb-manufacturer-product-candidates-enersys-wave179-2026-07-29.json","description":"docs/imports/rb-source-backed-description-drafts-enersys-wave179-2026-07-29.json","source":"docs/imports/rb-manufacturer-series-enersys-wave179-source.json","url":"https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-ft/amer/powersafe_vfrontterminal_batteryrangesummary.pdf"},
 "PowerSafe SBS":{"count":32,"identity":"docs/imports/rb-manufacturer-product-candidates-enersys-wave183-2026-07-29.json","description":"docs/imports/rb-source-backed-description-drafts-enersys-wave183-2026-07-29.json","source":"docs/imports/rb-manufacturer-series-enersys-wave183-source.json","url":"https://www.enersys.com/4aaf7f/globalassets/documents/product-documentation/powersafe/sbs/amer/Powersafe_SBS_Top_Terminal_Range_Summary_amer_en_rs_ps_sbs_tt_1022.pdf"},
 "PowerSafe RH":{"count":19,"identity":"docs/imports/rb-manufacturer-product-candidates-enersys-rh-wave193-2026-07-29.json","description":"docs/imports/rb-source-backed-description-drafts-enersys-rh-wave193-2026-07-29.json","source":"docs/imports/rb-manufacturer-series-enersys-rh-wave193-source.json","url":"https://www.enersys.com/493c0d/globalassets/documents/product-documentation/powersafe/nicd/amer/us-rh-rs-003_0114.pdf"},
}
FIELDS=["scope_order","external_id","name","mpn","series","source_url","source_pin_path","source_pin_sha256","source_reuse","prior_identity_action_path","prior_identity_action_sha256","prior_description_action_path","prior_description_action_sha256","live_exact_owner_count","live_exact_owner_external_ids","live_1c_owner_count","duplicate_decision","identity_action","description_action","prior_media_candidate_sha256","prior_visual_decision","media_decision","final_decision","hold_reason"]

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def group(row):
 n=row["name"]
 if row["product_external_id"].startswith("bitrix:"): return "Cyclon"
 if "12HX" in row["mpn"]: return "DataSafe HX"
 if row["mpn"].startswith("12V"): return "PowerSafe V-FT"
 if row["mpn"].startswith("SBS "): return "PowerSafe SBS"
 if row["mpn"].startswith("RH "): return "PowerSafe RH"
 raise SystemExit(f"Unknown EnerSys series: {row['product_external_id']}")

def ids_in(path:Path)->set[str]:
 d=json.loads(path.read_text(encoding="utf-8-sig")); return {r.get("external_id") for r in d.get("products",[]) if isinstance(r,dict)}

def main():
 rows=[r for r in csv.DictReader(SCOPE.open(encoding="utf-8-sig",newline="")) if r["partition"]=="enersys"]
 if len(rows)!=92 or [int(r["scope_order"]) for r in rows]!=list(range(1,93)): raise SystemExit("Wave246A scope/cardinality/order drift")
 if any((r["has_applied_description"],r["has_verified_published_image"],r["identity_fields_present"])!=("true","false","2") for r in rows): raise SystemExit("Wave246A pending-gap state drift")
 counts=Counter(group(r) for r in rows)
 if counts!={k:v["count"] for k,v in GROUPS.items()}: raise SystemExit(f"Series cardinality drift: {counts}")
 live={r["external_id"]:r for r in json.loads(LIVE.read_text(encoding="utf-8"))["rows"]}
 terms=json.loads(TERMS.read_text(encoding="utf-8")); terms_path=ROOT/terms["local_path"]
 if sha(terms_path)!=terms["sha256"]: raise SystemExit("Terms snapshot SHA drift")
 visual={r["external_id"]:r for r in csv.DictReader(PRIOR_VISUAL.open(encoding="utf-8-sig",newline=""))}
 source_registry=[]
 for key,cfg in GROUPS.items():
  source=ROOT/cfg["source"]
  source_registry.append({"series":key,"rows":cfg["count"],"source_url":cfg["url"],"pin_path":cfg["source"],"pin_sha256":sha(source),"reuse_status":"REUSED_NO_REDOWNLOAD","visual_check":"Cyclon pages 11, 15, 17 and 18 rendered and checked" if key=="Cyclon" else "prior exact-table manifest/report reused; no source bytes redownloaded"})
 source_registry.append({"series":"all","rows":92,"source_url":terms["source_url"],"pin_path":terms["local_path"],"pin_sha256":terms["sha256"],"reuse_status":"NEW_RIGHTS_SOURCE","rights_finding":terms["rights_finding"]})
 evidence=[]; media=[]; dup=[]
 for row in rows:
  key=group(row); cfg=GROUPS[key]
  if row["product_external_id"] not in ids_in(ROOT/cfg["identity"]) or row["product_external_id"] not in ids_in(ROOT/cfg["description"]): raise SystemExit(f"Prior action coverage missing: {row['product_external_id']}")
  lr=live[row["product_external_id"]]
  exact=[h for h in lr["hits"] if ''.join(c for c in (h.get("mpn") or '').casefold() if c.isalnum())==''.join(c for c in row["mpn"].casefold() if c.isalnum())]
  one_c=[h for h in exact if h["namespace"]=="1c"]
  duplicate_decision="PASS_UNIQUE_EXACT_OWNER" if len(exact)==1 and exact[0]["external_id"]==row["product_external_id"] else "HOLD_EXACT_OWNER_AMBIGUITY"
  prior=visual.get(row["product_external_id"])
  if prior:
   media_reason="PRIOR_COMPANY_OWNED_CANDIDATE_NOT_VISUALLY_EXACT"
  else:
   media_reason="NO_EXACT_MODEL_MEDIA_CANDIDATE"
  hold=media_reason+"|ENERSYS_TERMS_NO_COMMERCIAL_IMAGE_REUSE_WITHOUT_PERMISSION"
  record={"scope_order":row["scope_order"],"external_id":row["product_external_id"],"name":row["name"],"mpn":row["mpn"],"series":key,"source_url":cfg["url"],"source_pin_path":cfg["source"],"source_pin_sha256":sha(ROOT/cfg["source"]),"source_reuse":"true","prior_identity_action_path":cfg["identity"],"prior_identity_action_sha256":sha(ROOT/cfg["identity"]),"prior_description_action_path":cfg["description"],"prior_description_action_sha256":sha(ROOT/cfg["description"]),"live_exact_owner_count":len(exact),"live_exact_owner_external_ids":"|".join(h["external_id"] for h in exact),"live_1c_owner_count":len(one_c),"duplicate_decision":duplicate_decision,"identity_action":"SKIP_ALREADY_APPLIED","description_action":"SKIP_ALREADY_APPLIED","prior_media_candidate_sha256":prior["asset_sha256"] if prior else "","prior_visual_decision":prior["visual_decision"] if prior else "NO_CANDIDATE","media_decision":"HOLD","final_decision":"HOLD","hold_reason":hold}
  evidence.append(record)
  media.append({"external_id":record["external_id"],"mpn":record["mpn"],"series":key,"candidate_sha256":record["prior_media_candidate_sha256"],"visual_status":record["prior_visual_decision"],"rights_source_url":terms["source_url"],"rights_snapshot_path":terms["local_path"],"rights_snapshot_sha256":terms["sha256"],"decision":"HOLD","promotion_allowed":False,"reason":hold})
  dup.append({"external_id":record["external_id"],"mpn":record["mpn"],"exact_owners":exact,"one_c_owner_external_ids":[h["external_id"] for h in one_c],"decision":duplicate_decision,"collapse_action":False})
 with LEDGER.open("w",encoding="utf-8-sig",newline="") as h:w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator="\n");w.writeheader();w.writerows(evidence)
 MEDIA.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","decisions":media},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 DUPLICATES.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","decisions":dup,"collapse_manifest_created":False,"database_operations":0},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 ACTIONS.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","identity_manifest_created":False,"description_manifest_created":False,"identity_rows":0,"description_rows":0,"reason":"all 92 rows already have both identity fields and an applied source-backed description; no-repeat gate forbids persistent restaging manifests","laravel_validation":{"temporary_identity_subset_rows":15,"identity_dry_run":"PASS","temporary_description_subset_rows":92,"description_dry_run":"PASS_92_UNCHANGED_NONE_PUBLISHED","temporary_manufacturer_preview_subset_rows":77,"preview_read_only_verifier":"PASS"},"apply":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 SOURCES.write_text(json.dumps({"schema_version":1,"site_key":"microchips-by","sources":source_registry},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 summary={"schema_version":1,"wave":"wave246a_enersys","checked_at":"2026-07-30","scope":{"rows":92,"series":dict(counts)},"no_repeat":{"prior_identity_covered":92,"prior_description_covered":92,"new_identity_manifest_rows":0,"new_description_manifest_rows":0},"sources":{"reused":5,"new":1,"redownloaded_family_sources":0},"live":{"unique_exact_owner":sum(r["duplicate_decision"]=="PASS_UNIQUE_EXACT_OWNER" for r in evidence),"one_c_owner_conflicts":sum(int(r["live_1c_owner_count"])>0 for r in evidence)},"decisions":{"PASS":0,"HOLD":92,"media_hold":92,"duplicate_pass":sum(r["duplicate_decision"]=="PASS_UNIQUE_EXACT_OWNER" for r in evidence)},"database_operations":0}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 REPORT.write_text(f"""# Wave246A — EnerSys pending B2B media scope

Scope строго равен 92 строкам `partition=enersys` из `rb-wave246-b2b-scope.csv`: Cyclon 15, DataSafe HX 17, PowerSafe V-FT 9, PowerSafe SBS 32, PowerSafe RH 19.

No-repeat scan показал, что identity и source-backed description уже выполнены для 92/92 строк в waves 179/183/193/209A/241. Поэтому новые identity/description manifests не создавались: stageable rows = 0. Все 92 строки действительно остаются pending только по media (`has_verified_published_image=false`).

Пять ранее зафиксированных manufacturer-primary family sources переиспользованы без повторной загрузки. Cyclon PDF SHA-256 `3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f`; страницы 11, 15, 17, 18 отрендерены и визуально проверены. Новый источник только один: официальный EnerSys Terms of Use, SHA-256 `{terms['sha256']}`. Он разрешает лишь personal/non-commercial use и не даёт права коммерчески публиковать отдельные изображения без письменного разрешения.

Live read-only snapshot: 92/92 имеют ровно одного exact normalized EnerSys+MPN owner; exact 1C conflicts = 0; duplicate collapse actions = 0. Prefix-пары вроде `12V100F`/`12V100FC` и `SBS 30`/`SBS 300` не считаются дублями.

Итог: PASS 0, HOLD 92. Для девяти scope Cyclon rows уже существующие company-owned candidates ранее получили visual HOLD из-за нечитаемой/неполной маркировки; для остальных exact model media candidate отсутствует. Дополнительно официальный rights gate запрещает promotion manufacturer assets. Media manifests на импорт не создавались.

Laravel validation выполнена через временные (не import) subsets: identity dry-run для 15 Bitrix rows — PASS, 0 commercial/publication changes; description dry-run для всех 92 — 92 unchanged, none published; read-only manufacturer preview verifier для остальных 77 — PASS. Постоянные повторные identity/description manifests не создавались. Apply/commit/push не выполнялись.
""",encoding="utf-8")
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
