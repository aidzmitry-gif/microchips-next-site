#!/usr/bin/env python3
"""Read-only Wave226 profile for unreviewed company-owned legacy preview media."""
from __future__ import annotations
import base64,csv,hashlib,json,subprocess
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'
QUEUE=GEN/'rb-enrichment-queue-wave226.csv'; W225=GEN/'rb-wave225a-preview-image-review-queue.csv'; OUT=GEN/'rb-wave227a-media-profile.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def live():
 php="""$scope=app('db')->table('product_description_drafts')->select('product_id','identity_scope')->whereIn('identity_scope',['exact','model_core'])->where('source_tier','manufacturer_primary')->orderBy('product_id')->orderByDesc('id')->get()->groupBy('product_id')->map(fn($r)=>$r->first()->identity_scope);$rows=app('db')->table('product_media as pm')->join('products as p','p.id','=','pm.product_id')->where('pm.kind','image')->where('pm.verification_status','legacy_exact_preview')->where('pm.is_published',true)->whereNotNull('pm.storage_path')->whereNotNull('pm.rights_basis')->whereRaw(\"lower(pm.rights_basis) like '%%company-owned%%'\")->select('p.id as product_id','p.external_id','pm.id as media_id','pm.content_sha256 as hash','pm.storage_path','pm.rights_basis')->orderBy('p.external_id')->orderBy('pm.id')->get()->map(function($r)use($scope){$paths=[storage_path('app/private/'.$r->storage_path),storage_path('app/public/'.$r->storage_path)];$path=collect($paths)->first(fn($x)=>is_file($x));$r->identity_scope=$scope->get($r->product_id);$r->file_exists=$path!==null;$r->file_sha256=$path===null?'':hash_file('sha256',$path);return $r;});echo json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"""
 result=subprocess.run(['docker','compose','exec','-T','backend','php','artisan','tinker',f"--execute=eval(base64_decode('{base64.b64encode(php.encode()).decode()}'));"],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if result.returncode:raise SystemExit(result.stderr or result.stdout)
 return json.loads(result.stdout)
def main():
 queue=read(QUEUE);byid={r['product_external_id']:r for r in queue}
 if len(queue)!=1486 or len(byid)!=1486:raise SystemExit('Wave226 queue drift')
 reviewed={r['product_external_id'] for r in read(W225) if r['partition']=='displayable_preview_requires_human_review'}
 repeat=set(byid)&reviewed; remaining=set(byid)-reviewed
 live_rows=[r for r in live() if r['external_id'] in remaining]; per=defaultdict(list)
 for r in live_rows:per[r['external_id']].append(r)
 eligible=[]
 for eid,rs in per.items():
  # A safe OCR batch requires one unambiguous asset, a first-party bounded identity,
  # an actual local file and a matching recorded hash.
  if len(rs)==1 and rs[0]['identity_scope'] in {'exact','model_core'} and rs[0]['file_exists'] and rs[0]['hash'] and rs[0]['file_sha256']==rs[0]['hash']:
   eligible.append(eid)
 def group(ids,key):return dict(sorted(Counter(byid[x][key] or '(unresolved)' for x in ids).items()))
 display=set(per)
 file_ok={eid for eid,rs in per.items() if len(rs)==1 and rs[0]['file_exists'] and rs[0]['hash'] and rs[0]['file_sha256']==rs[0]['hash']}
 scoped={eid for eid,rs in per.items() if len(rs)==1 and rs[0]['identity_scope'] in {'exact','model_core'}}
 summary={'schema_version':1,'batch':'wave227a_wave226_media_profile','mode':'read_only','queue':{'path':QUEUE.relative_to(ROOT).as_posix(),'sha256':sha(QUEUE),'rows':len(queue),'unique_ids':len(byid)},'wave225_exclusion':{'path':W225.relative_to(ROOT).as_posix(),'sha256':sha(W225),'reviewed_ids':len(reviewed),'overlap_excluded_ids':len(repeat),'remaining_ids':len(remaining)},'company_owned_legacy_exact_preview':{'media_rows':len(live_rows),'products':len(display),'single_media_products':sum(len(v)==1 for v in per.values()),'identity_scoped_products':len(scoped),'identity_scope_counts':dict(sorted(Counter((rs[0]['identity_scope'] or 'none') if len(rs)==1 else 'multiple_media' for rs in per.values()).items())),'local_file_hash_matched_products':len(file_ok),'safe_ocr_eligible_products':len(eligible),'by_manufacturer':group(eligible,'manufacturer'),'by_category':group(eligible,'category_external_id')},'recommended_largest_safe_ocr_batch':min(100,len(eligible)),'recommendation':'Use only the single-media, identity-scoped, hash-matched subset; retain every other row as HOLD.','database_mutations':0,'apply_performed':False}
 OUT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
