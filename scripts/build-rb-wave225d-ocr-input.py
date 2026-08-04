#!/usr/bin/env python3
"""Create fail-closed OCR input from the human-review-only Wave225-A media queue."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'
QUEUE=GEN/'rb-wave225a-preview-image-review-queue.csv'; DEFAULT_ASSETS=ROOT/'.tmp/wave225-assets'
OUT=GEN/'rb-wave225-ocr-input.csv'; HOLD=GEN/'rb-wave225-ocr-hold-ledger.csv'; SUMMARY=GEN/'rb-wave225-ocr-input.summary.json'
OCR_FIELDS=['external_id','media_id','image_path','expected_mpn','expected_model_core','manufacturer','hash']
HOLD_FIELDS=['external_id','media_id','storage_path','expected_mpn','expected_model_core','manufacturer','hash','hold_reason']
def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rows(p:Path)->list[dict[str,str]]:
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def write_csv(p:Path,fields:list[str],data:list[dict[str,str]])->None:
 with p.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data)
def validate_row(r:dict[str,str],root:Path)->tuple[dict[str,str]|None,dict[str,str]|None]:
 eid=r['product_external_id']; media_id=r.get('media_ids',''); storage=r.get('storage_paths',''); digest=r.get('media_hashes','').lower()
 mpn=r.get('mpn','').strip(); core=r.get('model_core','').strip(); base={'external_id':eid,'media_id':media_id,'storage_path':storage,'expected_mpn':mpn,'expected_model_core':core,'manufacturer':r.get('manufacturer',''),'hash':digest}
 reason=''
 if r.get('review_status')!='pending_human_review' or r.get('auto_pass')!='false':reason='review_state_is_not_pending_human_review'
 elif r.get('media_metadata_count')!='1' or any(';' in x or '|' in x for x in (media_id,storage,digest)):reason='multiple_or_delimited_media_metadata'
 elif bool(mpn)==bool(core):reason='expected_identity_must_contain_exactly_one_of_mpn_or_model_core'
 elif not media_id or not digest or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):reason='missing_or_invalid_media_hash'
 else:
  ext=Path(storage).suffix.lower().lstrip('.')
  if not ext:reason='storage_path_has_no_extension'
  else:
   asset=(root/f'{media_id}.{ext}').resolve()
   if root not in asset.parents:reason='asset_path_escapes_supplied_root'
   elif not asset.is_file():reason='local_asset_missing'
   elif sha(asset)!=digest:reason='local_asset_sha256_mismatch'
 if reason:return None,{**base,'hold_reason':reason}
 return {'external_id':eid,'media_id':media_id,'image_path':str(asset),'expected_mpn':mpn,'expected_model_core':core,'manufacturer':r.get('manufacturer',''),'hash':digest},None
def build(queue_path:Path,assets_root:Path,out:Path,hold:Path,summary:Path)->dict:
 root=assets_root.resolve(); candidates=[r for r in rows(queue_path) if r.get('partition')=='displayable_preview_requires_human_review']
 if len(candidates)!=125 or len({r['product_external_id'] for r in candidates})!=125:raise ValueError('Wave225 displayable-preview scope drift')
 ready=[]; held=[]
 for r in candidates:
  passed,held_row=validate_row(r,root)
  if passed is not None:ready.append(passed)
  else:held.append(held_row)
 write_csv(out,OCR_FIELDS,ready);write_csv(hold,HOLD_FIELDS,held)
 result={'schema_version':1,'batch':'wave225d_ocr_input','queue':{'path':str(queue_path),'sha256':sha(queue_path),'displayable_preview_rows':125},'assets_root':str(root),'ocr_input':{'path':str(out),'sha256':sha(out),'rows':len(ready),'fields':OCR_FIELDS},'hold_ledger':{'path':str(hold),'sha256':sha(hold),'rows':len(held),'reason_counts':{k:sum(x['hold_reason']==k for x in held) for k in sorted({x['hold_reason'] for x in held})}},'policy':{'ocr_verdicts_created':0,'auto_pass':False,'database_apply':False,'publication_changes':0,'commit_or_push':False}}
 summary.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--assets-root',type=Path,default=DEFAULT_ASSETS);p.add_argument('--queue',type=Path,default=QUEUE);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--hold',type=Path,default=HOLD);p.add_argument('--summary',type=Path,default=SUMMARY);a=p.parse_args()
 print(json.dumps(build(a.queue,a.assets_root,a.out,a.hold,a.summary),ensure_ascii=False))
if __name__=='__main__':main()
