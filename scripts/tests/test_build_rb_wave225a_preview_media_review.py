import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/'docs/audits/generated'
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def test_wave225a_exact_scope_and_readiness_partition():
 q=rows(GEN/'rb-wave225a-preview-image-review-queue.csv'); s=json.loads((GEN/'rb-wave225a-preview-image-review.summary.json').read_text(encoding='utf-8'))
 assert len(q)==len({x['product_external_id'] for x in q})==334
 assert sum(x['partition']=='displayable_preview_requires_human_review' for x in q)==125
 assert sum(x['partition']=='missing_preview_media_hold' for x in q)==209
 assert s['wave224_scope']['by_manifest']=={'wave224a':40,'wave224b':294}
def test_wave225a_pinned_media_schema_and_no_automatic_pass():
 q=rows(GEN/'rb-wave225a-preview-image-review-queue.csv'); media=rows(GEN/'rb-wave225a-product-media-export.csv'); s=json.loads((GEN/'rb-wave225a-preview-image-review.summary.json').read_text(encoding='utf-8'))
 assert s['pinned_media_export']['fields']==['external_id','media_id','hash','storage_path','rights_basis','dimensions']
 assert list(media[0])==s['pinned_media_export']['fields'] and len(media)==125
 assert all(x['review_status']=='pending_human_review' and x['auto_pass']=='false' and x['review_reason'] for x in q)
 assert all((x['model_core'] and not x['mpn']) or (x['mpn'] and not x['model_core']) for x in q)
 assert all(x['media_metadata_count']!='0' for x in q if x['partition']=='displayable_preview_requires_human_review')
 assert all(x['media_metadata_count']=='0' for x in q if x['partition']=='missing_preview_media_hold')
 assert s['policy']=={'auto_pass':False,'automatic_media_promotion':False,'database_apply':False,'publication_changes':0,'commit_or_push':False}
