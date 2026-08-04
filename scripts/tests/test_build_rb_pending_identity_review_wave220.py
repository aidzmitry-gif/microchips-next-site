import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
def test_wave220_is_bounded_deterministic_and_fail_closed():
 s=json.loads((GEN/'rb-pending-identity-review-wave220-summary.json').read_text(encoding='utf-8'))
 assert s['rows']==50 and s['same_identity_confirmed']==0 and s['database_mutations']==0
 assert s['review_command_eligible_rows']+s['deferred_rows']==50
 assert len(s['manifests'])==0
 for x in s['manifests']:
  assert x['mode']=='dry_run' and x['catalog_entity_mutations']==0 and x['apply_flag_used'] is False
def test_wave220_manifest_policy_and_pinned_evidence():
 for p in sorted(IMP.glob('rb-pending-identity-review-wave220-2026-07-29-batch-*.json')):
  m=json.loads(p.read_text(encoding='utf-8')); assert 1<=m['expected_count']<=22
  assert m['mutation_policy']=={'change_products':False,'change_site_links':False,'merge_products':False,'delete_products':False,'change_publication':False,'change_urls':False,'change_seo':False,'change_media':False}
  assert len(m['decisions'])==m['expected_count'] and all(d['decision'] in {'hold','different_product_false_mapping'} and len(d['legacy_text_sha256'])==64 for d in m['decisions'])
