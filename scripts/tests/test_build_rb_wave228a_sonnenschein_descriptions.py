import csv,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];GEN=ROOT/'docs/audits/generated';IMP=ROOT/'docs/imports'
def test_wave228a_scope_pins_and_nonrepeat_hold():
 s=json.loads((GEN/'rb-wave228a-sonnenschein-description.summary.json').read_text(encoding='utf-8'));m=json.loads((IMP/'rb-source-backed-description-stage-manifest-wave228a-2026-07-29.json').read_text(encoding='utf-8'))
 assert (s['target_rows'],s['reused_wave211c_official_source_rows'],s['new_exact_source_rows'],s['stageable_exact_source_rows'],s['official_source_absent_holds'])==(28,18,10,28,0)
 assert s['stage_contract']=={'refresh_existing_required':True,'refresh_applied_required':True,'legacy_evidence_upgrade_only':True}
 assert len(m['products'])==28 and all(x['external_id'].startswith('bitrix:') and x['identity_scope']==x['evidence_scope']=='model_core' and x['technical_attributes'] for x in m['products'])
 assert all('current_name' not in x and set(x)=={'external_id','manufacturer','model_core','technology','source_url','technical_attributes','source_kind','source_tier','source_publisher','manufacturer_primary','evidence_scope','identity_scope','checked_at'} for x in m['products'])
 for x in s['source_registry'].values():assert hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest()==x['sha256']
