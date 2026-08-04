#!/usr/bin/env python3
"""Prepare conservative, batched review decisions for the first 50 pending Bitrix links."""
from __future__ import annotations
import base64, hashlib, json, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
PREFIX='rb-pending-identity-review-wave220-2026-07-29'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if r.returncode: raise SystemExit(r.stderr or r.stdout)
 return r.stdout
def live():
 php="""$c=app('db')->table('catalog_identity_candidates as c')->join('one_c_nomenclature_items as o','o.id','=','c.one_c_nomenclature_item_id')->leftJoin('products as p','p.external_id','=','o.external_id')->select('c.id','c.legacy_id','c.source_payload','c.source_checksum','o.external_id as one_c_external_id','o.name as one_c_name','p.id as product_id','p.name as product_name','p.manufacturer','p.mpn')->where('c.review_status','pending')->orderBy('c.id')->limit(50)->get();$ids=$c->pluck('legacy_id')->map(fn($x)=>'bitrix:'.$x)->all();$r=app('db')->table('staged_import_records as s')->join('import_runs as i','i.id','=','s.import_run_id')->select('s.import_run_id','s.entity_type','s.external_id','s.payload','i.source','i.summary')->whereIn('s.external_id',$ids)->whereIn('s.entity_type',['bitrix_legacy_product_evidence','bitrix_duplicate_review_decision'])->orderBy('s.entity_type')->orderBy('s.external_id')->get();echo json_encode(['candidates'=>$c,'records'=>$r],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"""
 b=base64.b64encode(php.encode()).decode(); out=run(['docker','compose','exec','-T','backend','php','artisan','tinker',f"--execute=eval(base64_decode('{b}'));"])
 return json.loads(out)
def cap(s):
 m=re.search(r'(\d+(?:[.,]\d+)?)\s*(?:a[hc]|ач|ah)',s,re.I); return float(m.group(1).replace(',','.')) if m else None
def model(s):
 # A bounded model-like signature is evidence for a candidate, never a promotion.
 return ''.join(re.findall(r'[A-ZА-Я0-9]+',s.upper()))
def main():
 d=live(); cs=d['candidates']; rec=defaultdict(dict)
 for x in d['records']: rec[x['external_id']][x['entity_type']]=x
 if len(cs)!=50 or len({x['id'] for x in cs})!=50: raise SystemExit('pending scope drift')
 prepared=[]; ledger=[]; deferred=[]
 for c in cs:
  p=json.loads(c['source_payload']); key='bitrix:'+str(c['legacy_id']); rs=rec[key]
  snap=rs.get('bitrix_legacy_product_evidence'); dup=rs.get('bitrix_duplicate_review_decision')
  if not snap: raise SystemExit('missing snapshot '+key)
  sp=json.loads(snap['payload']); dp=json.loads(dup['payload']) if dup else {}
  legacy=p.get('Название сайта',''); one=c['one_c_name']; lc,oc=cap(legacy),cap(one)
  conflict=lc is not None and oc is not None and lc!=oc
  decision='different_product_false_mapping' if conflict else 'hold'
  exact_queue=dp.get('group_decision')=='single_high_signal_review_queue' and dp.get('member_decision')=='review_exact_identity_candidate'
  relation=('material_capacity_conflict' if conflict else ('exact_textual_identity_candidate_primary_source_missing' if model(legacy) in model(one) or model(one) in model(legacy) else 'ambiguous_name_similarity')) if exact_queue else 'not_in_duplicate_exact_review_queue'
  row={'candidate_id':c['id'],'legacy_element_id':int(c['legacy_id']),'one_c_external_id':c['one_c_external_id'],'legacy_text_sha256':sp.get('legacy_text_sha256'),'decision':decision,'identity_scope':relation,'reason':('legacy and 1C capacity differ; no merge is permitted' if conflict else 'no pinned first-party source + ProductIdentityGuard proof; held to avoid duplicate promotion'),'checked_at':'2026-07-29T00:00:00Z','snap':snap,'dup':dup}
  (prepared if exact_queue else deferred).append(row)
  ledger.append({'candidate_id':c['id'],'legacy_element_id':c['legacy_id'],'one_c_external_id':c['one_c_external_id'],'legacy_name':legacy,'one_c_name':one,'canonical_product_id':c['product_id'],'canonical_product_name':c['product_name'],'canonical_manufacturer':c['manufacturer'],'canonical_mpn':c['mpn'],'relation':relation,'decision':decision,'review_command_eligible':exact_queue,'snapshot_run_id':snap['import_run_id'],'duplicate_run_id':dup['import_run_id'] if dup else None})
 if any(not x['legacy_text_sha256'] or len(x['legacy_text_sha256'])!=64 for x in prepared): raise SystemExit('invalid legacy hash')
 manifests=[]
 for n,start in enumerate(range(0,len(prepared),22),1):
  part=prepared[start:start+22]; sids={x['snap']['import_run_id'] for x in part}; dids={x['dup']['import_run_id'] for x in part}
  if len(sids)!=1 or len(dids)!=1: raise SystemExit('mixed evidence runs in batch')
  sm=json.loads(part[0]['snap']['summary']); dm=json.loads(part[0]['dup']['summary'])
  decisions=[]
  for priority,x in enumerate(part,1):
   decisions.append({k:x[k] for k in ('legacy_element_id','one_c_external_id','legacy_text_sha256','decision','identity_scope','reason','checked_at')}|{'review_priority':priority})
  counts=dict(sorted(Counter(x['decision'] for x in part).items()))
  m={'schema_version':1,'site_key':'microchips-by','review_batch':f'{PREFIX}-batch-{n:02d}','source_snapshot_run_id':sids.pop(),'source_snapshot_manifest_sha256':sm['manifest_sha256'],'source_duplicate_evidence_run_id':dids.pop(),'source_duplicate_manifest_sha256':dm['manifest_sha256'],'expected_count':len(part),'decision_counts':counts,'mutation_policy':{'change_products':False,'change_site_links':False,'merge_products':False,'delete_products':False,'change_publication':False,'change_urls':False,'change_seo':False,'change_media':False},'decisions':decisions}
  path=IMP/f'{PREFIX}-batch-{n:02d}.json'; path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); manifests.append(path)
 dry=[]
 for p in manifests:
  target='/tmp/'+p.name; run(['docker','compose','cp',str(p),'backend:'+target])
  out=run(['docker','compose','exec','-T','backend','php','artisan','catalog:apply-bitrix-identity-review-decisions',target])
  parsed=json.loads(out); 
  if parsed.get('mode')!='dry_run' or parsed.get('catalog_entity_mutations')!=0: raise SystemExit('dry-run guard failed')
  dry.append({'manifest':p.name,'manifest_sha256':sha(p),'mode':parsed['mode'],'reviewed':parsed.get('reviewed'),'catalog_entity_mutations':parsed.get('catalog_entity_mutations'),'apply_flag_used':False})
 GEN.mkdir(parents=True,exist_ok=True)
 (GEN/'rb-pending-identity-review-wave220-ledger.json').write_text(json.dumps({'mode':'read_only','database_mutations':0,'candidates':ledger},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 allrows=prepared+deferred
 summary={'schema_version':1,'scope':'first 50 pending catalog_identity_candidates ordered by id','rows':50,'review_command_eligible_rows':len(prepared),'deferred_rows':len(deferred),'decision_counts':dict(sorted(Counter(x['decision'] for x in allrows).items())),'relation_counts':dict(sorted(Counter(x['identity_scope'] for x in allrows).items())),'same_identity_confirmed':0,'manifests':dry,'database_mutations':0,'apply_flag_used':False,'policy':'No same_identity decision without a pinned first-party source and ProductIdentityGuard proof.'}
 (GEN/'rb-pending-identity-review-wave220-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 report=ROOT/'docs/audits/2026-07-29-rb-pending-identity-review-wave220.md'
 command_note=(str(len(prepared))+' rows have the exact duplicate-evidence contract required by the Laravel review command; their bounded manifest passed dry-run.' if prepared else 'No row has the exact duplicate-evidence contract required by the Laravel review command, so no invalid or fabricated manifest was submitted.')
 report.write_text('# Pending Bitrix identity review — 50 rows\n\nRead-only decision set for the first 50 pending candidates, deterministically ordered by candidate id. No candidate was promoted to `same_identity`: the pending queue’s snapshot/duplicate evidence is not first-party product proof and a duplicate-avoiding review must fail closed.\n\n- Decisions: '+json.dumps(summary['decision_counts'],ensure_ascii=False)+'.\n- Relation groups: '+json.dumps(summary['relation_counts'],ensure_ascii=False)+'.\n- '+command_note+' The other '+str(len(deferred))+' rows are held as not eligible for that command because they are absent from the exact-review queue.\n- No `--apply`, catalog, Product, SiteProduct, URL, SEO, media, publication, merge, or deletion mutation occurred.\n- Capacity conflicts are marked `different_product_false_mapping`; all other exact-looking/ambiguous title relations are held for source-backed review.\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__': main()
