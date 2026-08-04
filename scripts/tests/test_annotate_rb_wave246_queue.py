import csv, hashlib, json, subprocess, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
QUEUE=ROOT/"docs/audits/generated/rb-enrichment-queue-wave246.csv"
SUMMARY=ROOT/"docs/audits/generated/rb-enrichment-queue-wave246.summary.json"

def read_csv(path):
 with path.open(encoding="utf-8-sig",newline="") as h:return list(csv.DictReader(h))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def test_wave246_annotation_is_complete_truthful_and_idempotent():
 first=subprocess.run([sys.executable,str(ROOT/"scripts/annotate-rb-wave246-queue.py")],cwd=ROOT,capture_output=True,text=True)
 assert first.returncode==0,first.stderr
 queue_hash=digest(QUEUE); summary_hash=digest(SUMMARY)
 second=subprocess.run([sys.executable,str(ROOT/"scripts/annotate-rb-wave246-queue.py")],cwd=ROOT,capture_output=True,text=True)
 assert second.returncode==0,second.stderr
 assert digest(QUEUE)==queue_hash and digest(SUMMARY)==summary_hash
 rows=read_csv(QUEUE); ids=[r["product_external_id"] for r in rows]
 assert len(rows)==1236 and len(ids)==len(set(ids))
 counts=Counter(r["research_status"] for r in rows)
 assert counts["wave246a_hold_media_no_safe_mutation"]==92
 assert counts["wave246b_pass_dry_run_ready_not_applied"]==88
 assert counts["wave246b_hold_exact_owner_conflict"]==4
 assert counts["wave246c_noop_prior_reviewed_no_repeat"]==56
 assert counts["wave246c_hold_no_exact_media"]==36
 assert counts["wave246_media_visual_hold"]==5
 assert not any("applied" in r["research_status"] and "not_applied" not in r["research_status"] for r in rows if r["research_status"].startswith("wave246"))
 accounting=read_csv(ROOT/"docs/audits/generated/rb-wave246-scope-decision-accounting.csv")
 assert len(accounting)==276 and all(r["present_in_wave246_queue"]=="true" and r["membership_outcome"]=="annotated" for r in accounting)
 assert Counter(r["decision_source"] for r in accounting)=={"wave246a":92,"wave246b":92,"wave246c":92}
 summary=json.loads(SUMMARY.read_text(encoding="utf-8"))
 assert summary["membership_changes"]["prior_queue_records"]==1247
 assert summary["membership_changes"]["wave246_queue_records"]==1236
 assert summary["membership_changes"]["intersection"]==1236
 assert summary["membership_changes"]["added_count"]==0 and summary["membership_changes"]["removed_count"]==11
 reviewed=summary["reviewed_media"]
 assert reviewed["visual_pass"]==11 and reviewed["pass_still_present"]==0 and reviewed["promoted_retired_count"]==11
 assert set(reviewed["promoted_retired_external_ids"])==set(summary["membership_changes"]["removed_external_ids"])
 assert summary["scope_decision_accounting"]["frozen_scope_rows"]==summary["scope_decision_accounting"]["present_and_annotated"]==276
 assert summary["scope_decision_accounting"]["retired_from_queue"]==0
 assert summary["research_status_distribution"]==dict(sorted(counts.items()))
 assert summary["hashes"]["wave246_queue"]==digest(QUEUE)
