from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/build-rb-wave219b-high-source-evidence.py'
GEN=ROOT/'docs/audits/generated'
EVIDENCE=GEN/'rb-wave219b-high-source-evidence.csv'; SUMMARY=GEN/'rb-wave219b-high-source-evidence.summary.json'; MANIFEST=ROOT/'docs/imports/rb-verified-oem-identities-wave219b-high-source-2026-07-29.json'; LIVE=GEN/'wave219b-high-source-live-identity-collisions.json'; DRY=GEN/'wave219b-high-source-laravel-dry-run.json'
def rows():
 with EVIDENCE.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def test_wave219b_exact_union_and_determinism():
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 before=(hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 assert before==(hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 assert Counter(r['manufacturer_cluster'] for r in rows())=={'APC':6,'B.B. Battery':10,'CSB':13,'Delta':26,'Fiamm':2,'Sonnenschein':2,'Sprinter':1}
 assert len(rows())==len({r['product_external_id'] for r in rows()})==60
def test_wave219b_manifest_sources_collisions_and_dry_run():
 summary=json.loads(SUMMARY.read_text(encoding='utf-8')); manifest=json.loads(MANIFEST.read_text(encoding='utf-8')); live=json.loads(LIVE.read_text(encoding='utf-8')); dry=json.loads(DRY.read_text(encoding='utf-8'))
 assert summary['exact_source_rows']==17 and summary['pinned_primary_sources']>=10
 assert all(r['safe_to_apply']=='false' for r in rows() if r['partition']!='exact_safe')
 assert manifest['products']==[]
 assert Counter(r['partition'] for r in rows())['hold_importer_ineligible_not_bitrix_draft']==1
 assert live['mode']=='read_only' and live['database_mutations']==0
 assert dry['mode']=='dry_run' and dry['exit_code']==1 and dry['records']==0 and dry['expected_fail_closed_reason']=='empty_exact_safe_manifest'
 assert dry['manifest_sha256']==hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
 assert dry['database_mutations']==dry['commercial_fields_changed']==dry['publication_fields_changed']==0
