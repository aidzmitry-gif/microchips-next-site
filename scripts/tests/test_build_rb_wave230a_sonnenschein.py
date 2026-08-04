import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=R/'docs/audits/generated';I=R/'docs/imports'
def test_wave230a_frozen_scope_and_pinned_model_core_contract():
 s=json.loads((D/'rb-wave230a-sonnenschein.summary.json').read_text());m=json.loads((I/'rb-source-backed-description-stage-manifest-wave230a-2026-07-29.json').read_text())
 assert s['target_rows']==35 and s['exact_scope_rows']==0 and len(m['products'])==s['stageable_model_core']
 assert s['stageable_model_core']==33 and s['holds']==2
 assert 'bitrix:3117' not in {x['external_id'] for x in m['products']}
 assert all(x['identity_scope']==x['evidence_scope']=='model_core' and x['technical_attributes'] and x['source_url'].startswith('https://www.exidegroup.com/') for x in m['products'])
