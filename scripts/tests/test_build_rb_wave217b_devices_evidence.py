from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/build-rb-wave217b-devices-evidence.py"
EVIDENCE=ROOT/"docs/audits/generated/rb-wave217b-devices-evidence.csv"
SUMMARY=ROOT/"docs/audits/generated/rb-wave217b-devices-evidence.summary.json"
SOURCES=ROOT/"docs/audits/sources/wave217b-devices/source-registry.json"
MANIFEST=ROOT/"docs/imports/rb-verified-oem-identities-wave217b-devices-2026-07-29.json"
LIVE=ROOT/"docs/audits/generated/wave217b-devices-live-identity-collisions.json"
DRY=ROOT/"docs/audits/generated/wave217b-devices-laravel-dry-run.json"
CORRECTIONS=ROOT/"docs/audits/generated/wave217b-robiton-power-supply-category-candidates.csv"
MOVES=ROOT/"docs/imports/rb-site-category-move-wave217b-robiton-power-supplies.csv"
CATEGORY_DRY=ROOT/"docs/audits/generated/wave217b-robiton-power-supply-category-laravel-dry-run.json"
def rows():
 with EVIDENCE.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def test_wave217b_union_and_determinism():
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 before=(hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 assert before==(hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 assert Counter(r["manufacturer_cluster"] for r in rows())=={"Robiton":45,"Panasonic":10,"EnerSys":1}
 assert Counter(r["partition"] for r in rows())=={"hold_identity_collision":2,"hold_no_exact_primary_source":54}
def test_sources_manifest_and_scope():
 sources=json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
 assert len(sources)==2
 for source in sources:
  assert urlparse(source["source_url"]).scheme=="https"
  assert hashlib.sha256((ROOT/source["snapshot_path"]).read_bytes()).hexdigest()==source["snapshot_sha256"]
 assert json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]==[]
 assert all(x["safe_to_apply"]=="false" for x in rows() if x["partition"]!="exact_safe")
 with CORRECTIONS.open(encoding="utf-8-sig",newline="") as f: corrections=list(csv.DictReader(f))
 assert len(corrections)==29 and {x["product_external_id"] for x in corrections}=={x["product_external_id"] for x in rows() if x["product_class"]=="power supply"}
 assert all(x["current_category_external_id"]=="seo:chargers" and x["proposed_category_external_id"]=="seo:power-supplies" and x["safe_to_apply"]=="false" for x in corrections)
 with MOVES.open(encoding="utf-8",newline="") as f: moves=list(csv.DictReader(f))
 assert len(moves)==29 and list(moves[0])==["product_external_id","from_category_external_id","to_category_external_id"]
 assert {x["product_external_id"] for x in moves}=={x["product_external_id"] for x in corrections}
 assert all(x["from_category_external_id"]=="seo:chargers" and x["to_category_external_id"]=="seo:power-supplies" for x in moves)
def test_live_and_laravel_dry_run_guards():
 summary=json.loads(SUMMARY.read_text(encoding="utf-8"));live=json.loads(LIVE.read_text(encoding="utf-8"));dry=json.loads(DRY.read_text(encoding="utf-8"))
 assert summary["scope_exclusion"]=={"automotive_rows":0,"electronic_component_rows":0}
 assert live["mode"]=="read_only" and live["database_mutations"]==0
 assert {x["candidate_external_id"] for x in live["collisions"]}=={"bitrix:742","bitrix:3411"}
 assert dry["mode"]=="dry_run" and dry["exit_code"]==1 and dry["records"]==0 and dry["expected_fail_closed_reason"]=="empty_exact_safe_manifest"
 assert dry["manifest_sha256"]==hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
 assert dry["database_mutations"]==0
 category=json.loads(CATEGORY_DRY.read_text(encoding="utf-8"))
 assert category["mode"]=="dry_run" and category["exit_code"]==0 and category["records"]==29 and category["validation_error_count"]==0
 assert category["manifest_sha256"]==hashlib.sha256(MOVES.read_bytes()).hexdigest()
 assert category["category_link_mutations"]==category["url_mutations"]==category["canonical_mutations"]==category["publication_fields_changed"]==0
