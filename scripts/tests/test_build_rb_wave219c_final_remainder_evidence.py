from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/"docs/audits/generated"
EVIDENCE=GEN/"rb-wave219c-final-remainder-evidence.csv"; SUMMARY=GEN/"rb-wave219c-final-remainder-evidence.summary.json"; MANIFEST=ROOT/"docs/imports/rb-verified-oem-identities-wave219c-final-remainder-2026-07-29.json"; LIVE=GEN/"wave219c-final-remainder-live-identity-collisions.json"; DRY=GEN/"wave219c-final-remainder-laravel-dry-run.json"
def rows():
 with EVIDENCE.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def test_wave219c_exact_scope_type_and_taxonomy_ledger():
 data=rows(); assert len(data)==len({r["product_external_id"] for r in data})==57
 assert Counter(r["manufacturer_cluster"] for r in data)=={"Robiton":36,"Ventura":18,"Casil":1,"Contact":1,"Восток":1}
 assert any(r["taxonomy_assessment"]!="category_matches_product_type" for r in data)
 assert all(r["factual_product_type"] and r["extracted_model"] for r in data)
def test_wave219c_guards_manifest_and_dry_run():
 s=json.loads(SUMMARY.read_text(encoding="utf-8")); live=json.loads(LIVE.read_text(encoding="utf-8")); dry=json.loads(DRY.read_text(encoding="utf-8")); manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
 assert s["processed3500_overlap_ids"]==[] and s["scope_exclusion"]=={"automotive_rows":0,"electronics_rows":0}
 assert live["mode"]=="read_only" and live["candidate_rows_checked"]==57 and live["database_mutations"]==0
 assert dry["exit_code"]!=0 and dry["apply_flag_used"] is False and dry["records"]==len(manifest["products"])==0
 assert "non-empty products list" in (dry["stdout"]+dry["stderr"])
 assert dry["manifest_sha256"]==hashlib.sha256(MANIFEST.read_bytes()).hexdigest() and s["database_mutations"]==0
