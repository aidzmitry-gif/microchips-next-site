#!/usr/bin/env python3
"""Annotate Wave246 queue from frozen scope decisions without claiming no-op work was applied."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/"docs/audits/generated/rb-enrichment-queue-wave246.csv"
PRIOR=ROOT/"docs/audits/generated/rb-enrichment-queue-wave245.csv"
SCOPE=ROOT/"docs/audits/generated/rb-wave246-b2b-scope.csv"
A=ROOT/"docs/audits/generated/rb-wave246a-enersys-decision-ledger.csv"
B=ROOT/"docs/audits/generated/rb-wave246b-csb-evidence-ledger.csv"
C=ROOT/"docs/audits/generated/rb-wave246c-delta-leoch-decision-ledger.csv"
MEDIA=ROOT/"docs/audits/generated/rb-reviewed-legacy-preview-media-wave246.csv"
SUMMARY=ROOT/"docs/audits/generated/rb-enrichment-queue-wave246.summary.json"
ACCOUNTING=ROOT/"docs/audits/generated/rb-wave246-scope-decision-accounting.csv"
REPORT=ROOT/"docs/audits/2026-07-30-rb-wave246-queue-annotation.md"

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path:Path):
 with path.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def unique(items,key,label):
 values=[r[key] for r in items]
 if len(values)!=len(set(values)):raise SystemExit(f"{label} contains duplicate {key}")
 return set(values)

def main():
 queue=rows(QUEUE); prior=rows(PRIOR); scope=rows(SCOPE); a=rows(A); b=rows(B); c=rows(C); media=rows(MEDIA)
 qids=unique(queue,"product_external_id","Wave246 queue"); pids=unique(prior,"product_external_id","Wave245 queue"); sids=unique(scope,"product_external_id","Wave246 scope")
 if len(queue)!=1236 or len(prior)!=1247 or len(scope)!=276:raise SystemExit("Queue/scope cardinality drift")
 if Counter(r["partition"] for r in scope)!={"enersys":92,"csb":92,"delta_leoch":92}:raise SystemExit("Frozen partition cardinality drift")
 prior_status={r["product_external_id"]:r["research_status"] for r in prior}
 for row in queue:
  if row["product_external_id"] in prior_status:row["research_status"]=prior_status[row["product_external_id"]]
 decisions={}; sources={}
 if len(a)!=92 or {r["external_id"] for r in a}!={r["product_external_id"] for r in scope if r["partition"]=="enersys"}:raise SystemExit("Wave246A coverage drift")
 for r in a:
  if r["final_decision"]!="HOLD" or r["identity_action"]!="SKIP_ALREADY_APPLIED" or r["description_action"]!="SKIP_ALREADY_APPLIED":raise SystemExit("Unexpected Wave246A action semantics")
  decisions[r["external_id"]]="wave246a_hold_media_no_safe_mutation";sources[r["external_id"]]="wave246a"
 if len(b)!=92 or {r["external_id"] for r in b}!={r["product_external_id"] for r in scope if r["partition"]=="csb"}:raise SystemExit("Wave246B coverage drift")
 for r in b:
  if r["decision"]=="PASS":status="wave246b_pass_dry_run_ready_not_applied"
  elif r["decision"]=="HOLD":status="wave246b_hold_exact_owner_conflict"
  else:raise SystemExit(f"Unknown Wave246B decision {r['decision']}")
  decisions[r["external_id"]]=status;sources[r["external_id"]]="wave246b"
 if len(c)!=92 or {r["external_id"] for r in c}!={r["product_external_id"] for r in scope if r["partition"]=="delta_leoch"}:raise SystemExit("Wave246C coverage drift")
 for r in c:
  if r["overall_action"]=="NOOP_NO_NEW_SAFE_MUTATION":status="wave246c_noop_prior_reviewed_no_repeat"
  elif r["overall_action"]=="HOLD_MEDIA_GAP":status="wave246c_hold_no_exact_media"
  else:raise SystemExit(f"Unknown Wave246C action {r['overall_action']}")
  decisions[r["external_id"]]=status;sources[r["external_id"]]="wave246c"
 if set(decisions)!=sids or len(decisions)!=276:raise SystemExit("Not all frozen scope decisions are accounted")
 qmap={r["product_external_id"]:r for r in queue}
 for external_id,status in decisions.items():
  if external_id in qmap:qmap[external_id]["research_status"]=status
 media_pass=[];media_hold=[]
 for r in media:
  if r["visual_decision"]=="PASS_VISIBLE_EXACT_MPN":media_pass.append(r["external_id"])
  elif r["visual_decision"]=="HOLD":media_hold.append(r["external_id"])
  else:raise SystemExit(f"Unknown reviewed-media decision {r['visual_decision']}")
 if len(media_pass)!=11 or len(media_hold)!=5:raise SystemExit("Reviewed-media cardinality drift")
 for external_id in media_pass:
  if external_id in qmap:qmap[external_id]["research_status"]="wave246_media_pass_manifest_ready_not_applied"
 for external_id in media_hold:
  if external_id in qmap:qmap[external_id]["research_status"]="wave246_media_visual_hold"
 fieldnames=list(queue[0])
 with QUEUE.open("w",encoding="utf-8-sig",newline="") as h:w=csv.DictWriter(h,fieldnames=fieldnames,lineterminator="\n");w.writeheader();w.writerows(queue)
 accounting=[]
 scope_by_id={r["product_external_id"]:r for r in scope}
 for external_id in sorted(decisions,key=lambda x:(scope_by_id[x]["partition"],int(scope_by_id[x]["scope_order"]))):
  accounting.append({"partition":scope_by_id[external_id]["partition"],"scope_order":scope_by_id[external_id]["scope_order"],"product_external_id":external_id,"decision_source":sources[external_id],"assigned_status":decisions[external_id],"present_in_wave246_queue":str(external_id in qids).lower(),"membership_outcome":"annotated" if external_id in qids else "retired_from_queue"})
 with ACCOUNTING.open("w",encoding="utf-8-sig",newline="") as h:w=csv.DictWriter(h,fieldnames=list(accounting[0]),lineterminator="\n");w.writeheader();w.writerows(accounting)
 base=json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
 status_counts=dict(sorted(Counter(r["research_status"] for r in queue).items()))
 removed=sorted(pids-qids);added=sorted(qids-pids);retired_pass=sorted(set(media_pass)-qids);present_pass=sorted(set(media_pass)&qids)
 if len(removed)!=11 or added or set(removed)!=set(media_pass) or present_pass:raise SystemExit("Wave246 membership/media-promotion relationship drift")
 base.update({"annotation_schema_version":1,"membership_changes":{"prior_queue_records":len(prior),"wave246_queue_records":len(queue),"intersection":len(pids&qids),"added_count":len(added),"added_external_ids":added,"removed_count":len(removed),"removed_external_ids":removed},"scope_decision_accounting":{"frozen_scope_rows":276,"present_and_annotated":sum(x["present_in_wave246_queue"]=="true" for x in accounting),"retired_from_queue":sum(x["present_in_wave246_queue"]=="false" for x in accounting),"accounting_path":ACCOUNTING.relative_to(ROOT).as_posix(),"accounting_sha256":sha(ACCOUNTING)},"reviewed_media":{"reviewed_rows":16,"visual_pass":11,"visual_hold":5,"pass_still_present":len(present_pass),"pass_still_present_external_ids":present_pass,"promoted_retired_count":len(retired_pass),"promoted_retired_external_ids":retired_pass,"hold_still_present":sum(x in qids for x in media_hold)},"research_status_distribution":status_counts,"readiness":{"queue_records":len(queue),"remaining_gap_after_queue":base.get("remaining_gap_after_queue"),"current_content_complete_cards":base.get("current_content_complete_cards"),"target_content_complete_cards":base.get("target_content_complete_cards"),"readiness_distribution":base.get("readiness_distribution")},"hashes":{"wave245_queue":sha(PRIOR),"wave246_queue":sha(QUEUE),"frozen_scope":sha(SCOPE),"wave246a_ledger":sha(A),"wave246b_ledger":sha(B),"wave246c_ledger":sha(C),"reviewed_media_ledger":sha(MEDIA)}})
 SUMMARY.write_text(json.dumps(base,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 REPORT.write_text(f"""# Wave246 queue consolidation

Annotated queue: 1,236 unique rows. Wave245 intersection: 1,236; added: 0; removed: 11. All removed rows are exactly the 11 reviewed-media visual PASS products, so they are recorded as retired rather than falsely re-added or marked inside the queue.

All 276 frozen decisions are accounted: A 92 media holds/no-safe-mutation, B 88 dry-run-ready-not-applied plus 4 exact-owner holds, C 56 prior-reviewed no-repeat noops plus 36 media holds. No status claims apply where the ledger reports noop or dry-run only.

Five reviewed-media HOLD rows remain in the queue and are marked `wave246_media_visual_hold`. Research statuses from Wave245 are carried for every non-overridden intersection row.

Verification: exact queue cardinality 1,236; unique IDs; membership delta −11/+0; scope accounting 276/276; promoted-media retired 11/11. No DB/apply/commit/push.
""",encoding="utf-8")
 print(json.dumps({"queue_rows":len(queue),"status_distribution":status_counts,"scope_accounted":len(accounting),"removed":len(removed),"promoted_retired":len(retired_pass)},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
