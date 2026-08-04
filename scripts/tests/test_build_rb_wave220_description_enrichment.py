from __future__ import annotations
import csv,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/'docs/audits/generated'; SCRIPT=ROOT/'scripts/build-rb-wave220-description-enrichment.py'
OUT=GEN/'rb-wave220-description-enrichment-evidence.csv'; SUMMARY=GEN/'rb-wave220-description-enrichment.summary.json'; MANIFEST=ROOT/'docs/imports/rb-source-backed-description-drafts-wave220-2026-07-29.json'; LIVE=GEN/'wave220-description-enrichment-live-identity-guard.json'; DRY=GEN/'wave220-description-enrichment-stage-dry-run.json'
def rows():
 with OUT.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def test_wave220_union_and_determinism():
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 a=(hashlib.sha256(OUT.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True)
 assert a==(hashlib.sha256(OUT.read_bytes()).hexdigest(),hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
 assert Counter(r['wave'] for r in rows())=={'wave219b':17,'wave219c':17}
 assert Counter(r['content_contract_eligible'] for r in rows())=={'true':15,'false':19}
def test_wave220_manifest_guards_and_dry_run():
 m=json.loads(MANIFEST.read_text(encoding='utf-8'));s=json.loads(SUMMARY.read_text(encoding='utf-8'));l=json.loads(LIVE.read_text(encoding='utf-8'));d=json.loads(DRY.read_text(encoding='utf-8'))
 assert len(m['products'])==15 and all(r['identity_scope']=='model_core' and r['source_kind']=='official_manufacturer_catalogue' for r in m['products'])
 assert l['mode']=='read_only' and l['candidate_rows_checked']==34 and l['database_mutations']==0
 assert d['mode']=='dry_run' and d['exit_code']==0 and d['records']==15 and d['manifest_sha256']==hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
 assert d['database_mutations']==d['identity_fields_changed']==d['commercial_fields_changed']==d['publication_fields_changed']==d['url_mutations']==0
 assert s['content_contract']=={'catalogue_model_core_candidates':15,'held_official_product_pages':16,'held_model_core_boundary':3,'identity_scope':'model_core','identity_changes_proposed':0}
