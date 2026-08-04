import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
MANIFEST=IMP/'rb-source-backed-description-stage-manifest-wave224a-2026-07-29.json'
ALLOWED={'external_id','identity_scope','manufacturer','model_core','technology','source_url','technical_attributes','source_kind','source_tier','source_publisher','manufacturer_primary','evidence_scope','checked_at'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def test_wave224a_exact_scope_current_model_core_and_pins():
 m=json.loads(MANIFEST.read_text(encoding='utf-8')); s=json.loads((GEN/'rb-wave224a-description-stage-manifest.summary.json').read_text(encoding='utf-8'))
 assert len(m['products'])==len({x['external_id'] for x in m['products']})==40
 assert Counter(x['manufacturer'] for x in m['products'])=={'CSB':22,'EnerSys':18}
 assert s['scope']['model_core_matches_current_queue'] is True and s['candidate_evidence']['rows']==40
 for pin in s['pinned_source_registry']['files']:
  assert sha(ROOT/pin['path'])==pin['sha256']
def test_wave224a_has_only_stage_contract_fields_and_no_mutation_intent():
 m=json.loads(MANIFEST.read_text(encoding='utf-8')); s=json.loads((GEN/'rb-wave224a-description-stage-manifest.summary.json').read_text(encoding='utf-8'))
 for row in m['products']:
  assert set(row)==ALLOWED
  assert row['source_kind']=='official_manufacturer_product_page' and row['source_tier']=='manufacturer_primary'
  assert row['identity_scope']==row['evidence_scope']=='model_core' and row['manufacturer_primary'] is True
  assert row['source_url'].startswith('https://') and row['checked_at']=='2026-07-29'
  assert isinstance(row['technical_attributes'],dict) and row['technical_attributes'] and all(isinstance(k,str) and isinstance(v,str) and v for k,v in row['technical_attributes'].items())
 assert s['laravel_execution']['invoked'] is False
 assert s['intent']=={'price_changes':0,'stock_changes':0,'media_changes':0,'publication_changes':0,'url_changes':0,'identity_changes':0,'database_apply':False,'commit_or_push':False}
