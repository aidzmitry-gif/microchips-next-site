#!/usr/bin/env python3
"""Build the strictly human-reviewed preview-image queue from a pinned media CSV."""
from __future__ import annotations
import csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; IMP=ROOT/'docs/imports'; GEN=ROOT/'docs/audits/generated'
MANIFESTS=[('wave224a',IMP/'rb-source-backed-description-stage-manifest-wave224a-2026-07-29.json'),('wave224b',IMP/'rb-source-backed-description-stageable-wave224b-2026-07-29.json')]
READINESS=GEN/'rb-full-content-readiness-wave224-after.csv'; MEDIA=GEN/'rb-wave225a-product-media-export.csv'; OUT=GEN/'rb-wave225a-preview-image-review-queue.csv'; SUMMARY=GEN/'rb-wave225a-preview-image-review.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave225a-preview-image-review.md'
MEDIA_FIELDS=['external_id','media_id','hash','storage_path','rights_basis','dimensions']
FIELDS=['source_batch','source_manifest_sha256','product_external_id','name','category_external_id','manufacturer','identity_scope','model_core','mpn','source_url','source_kind','source_tier','source_publisher','checked_at','readiness_displayable_preview','partition','media_metadata_count','media_ids','media_hashes','storage_paths','rights_bases','dimensions','review_status','auto_pass','review_reason']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def sources():
 out={}
 for batch,p in MANIFESTS:
  raw=json.loads(p.read_text(encoding='utf-8-sig')); products=raw['products']
  expected=40 if batch=='wave224a' else 294
  if len(products)!=expected:raise SystemExit(f'{batch} scope drift')
  for r in products:
   eid=r['external_id']
   if eid in out:raise SystemExit(f'manifest overlap {eid}')
   scope=r['identity_scope']; model=r.get('model_core','') if scope=='model_core' else ''; mpn=r.get('mpn','') if scope=='exact' else ''
   if scope not in {'model_core','exact'} or not (model or mpn):raise SystemExit(f'identity scope drift {eid}')
   out[eid]={'source_batch':batch,'source_manifest_sha256':sha(p),'manufacturer':r['manufacturer'],'identity_scope':scope,'model_core':model,'mpn':mpn,'source_url':r['source_url'],'source_kind':r['source_kind'],'source_tier':r['source_tier'],'source_publisher':r['source_publisher'],'checked_at':r['checked_at']}
 if len(out)!=334:raise SystemExit('combined Wave224 ID scope drift')
 return out
def media_rows(p):
 got=rows(p)
 if not got or list(got[0].keys())!=MEDIA_FIELDS: raise SystemExit('pinned media export requires exact fields external_id, media_id, hash, storage_path, rights_basis, dimensions')
 seen=set()
 for r in got:
  key=(r['external_id'],r['media_id'])
  if not r['external_id'] or not r['media_id'] or key in seen:raise SystemExit('media export duplicate/blank identity')
  seen.add(key)
 return got
def main():
 source=sources(); readiness={r['product_external_id']:r for r in rows(READINESS)}
 if set(source)-set(readiness):raise SystemExit('readiness missing Wave224 ID')
 media=defaultdict(list)
 for r in media_rows(MEDIA):
  if r['external_id'] in source:media[r['external_id']].append(r)
 review=[]
 for eid,src in source.items():
  ready=readiness[eid]; display=ready['has_displayable_preview_image'].casefold()=='true'; part='displayable_preview_requires_human_review' if display else 'missing_preview_media_hold'; ms=media[eid]
  review.append({**src,'product_external_id':eid,'name':ready['name'],'category_external_id':ready['category_external_id'],'readiness_displayable_preview':'true' if display else 'false','partition':part,'media_metadata_count':str(len(ms)),'media_ids':'|'.join(x['media_id'] for x in ms),'media_hashes':'|'.join(x['hash'] for x in ms),'storage_paths':'|'.join(x['storage_path'] for x in ms),'rights_bases':'|'.join(x['rights_basis'] for x in ms),'dimensions':'|'.join(x['dimensions'] for x in ms),'review_status':'pending_human_review','auto_pass':'false','review_reason':'company-owned exact-media verification and visual identity review required; no automatic PASS'})
 review.sort(key=lambda r:(r['source_batch'],r['product_external_id']))
 with OUT.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(review)
 counts=Counter(r['partition'] for r in review)
 if counts!={'displayable_preview_requires_human_review':125,'missing_preview_media_hold':209}:raise SystemExit('readiness partition drift')
 summary={'schema_version':1,'batch':'wave225a_preview_image_review','wave224_scope':{'ids':len(source),'by_manifest':dict(sorted(Counter(r['source_batch'] for r in source.values()).items()))},'readiness':{'path':READINESS.relative_to(ROOT).as_posix(),'sha256':sha(READINESS),'displayable_preview_rows':125,'missing_preview_rows':209},'pinned_media_export':{'path':MEDIA.relative_to(ROOT).as_posix(),'sha256':sha(MEDIA),'fields':MEDIA_FIELDS,'rows':sum(len(v) for v in media.values()),'database_mutations':0},'review_queue':{'path':OUT.relative_to(ROOT).as_posix(),'sha256':sha(OUT),'rows':len(review),'partition_counts':dict(sorted(counts.items()))},'policy':{'auto_pass':False,'automatic_media_promotion':False,'database_apply':False,'publication_changes':0,'commit_or_push':False}}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave225-A preview-image review queue\n\nThe queue combines exactly 334 Wave224 source-evidence IDs (40 Wave224-A and 294 Wave224-B), joins the pinned Wave224 readiness snapshot and a read-only ProductMedia metadata export.\n\n- 125 rows have a displayable preview and are explicitly `pending_human_review`; they are never auto-PASS.\n- 209 rows lack a displayable preview and remain a media hold.\n- The queue preserves Wave224 A/B evidence, external ID, manufacturer, bounded model core or MPN, and source provenance. Media metadata is evidence only; no asset is copied, promoted, published or applied.\n',encoding='utf-8')
 print(json.dumps({'rows':len(review),'displayable':125,'missing':209,'database_mutations':0},ensure_ascii=False))
if __name__=='__main__':main()
