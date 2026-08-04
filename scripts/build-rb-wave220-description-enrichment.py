#!/usr/bin/env python3
"""Build conservative Russian description-draft evidence from Wave219 sources.

The existing staging contract accepts manufacturer-primary *catalogue* evidence
with model-core scope.  This wave deliberately does not relabel product-page
evidence as catalogue evidence, and never proposes identity, commercial,
publication, URL, or media changes.
"""
from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'
B=GEN/'rb-wave219b-high-source-evidence.csv'; C=GEN/'rb-wave219c-final-remainder-evidence.csv'
OUT=GEN/'rb-wave220-description-enrichment-evidence.csv'; SUMMARY=GEN/'rb-wave220-description-enrichment.summary.json'; LIVE=GEN/'wave220-description-enrichment-live-identity-guard.json'; DRY=GEN/'wave220-description-enrichment-stage-dry-run.json'
MANIFEST=ROOT/'docs/imports/rb-source-backed-description-drafts-wave220-2026-07-29.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave220-description-enrichment.md'
FIELDS=['wave','product_external_id','name','manufacturer','model_core','source_url','source_snapshot_path','source_snapshot_sha256','source_kind','content_contract_eligible','partition','hold_reason','safe_to_stage']
STAGING_MODEL_CORE_HOLDS={
 'КА-00004972':'legacy title has HRL12650W while the pinned catalogue proves only HRL12650; strict model-core boundaries reject suffix inference',
 'КА-00005320':'legacy title has HR1290W while the pinned catalogue proves only HR1290; strict model-core boundaries reject suffix inference',
 'КА-00005523':'legacy title has HRL12155W while the pinned catalogue proves only HRL12155; strict model-core boundaries reject suffix inference',
}
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p:Path)->list[dict[str,str]]:
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def norm(v:str)->str:return ''.join(c for c in (v or '').upper() if c.isalnum())
def live()->list[dict]:
 php="echo json_encode(app('db')->table('products')->select('external_id','name','manufacturer','mpn','sku','mpn_normalized','sku_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
 import base64
 r=subprocess.run(['docker','compose','exec','-T','backend','php','artisan','tinker',f"--execute=eval(base64_decode('{base64.b64encode(php.encode()).decode()}'));"],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if r.returncode or not r.stdout.strip().startswith('['):raise SystemExit(r.stderr.strip() or r.stdout.strip())
 rows=json.loads(r.stdout)
 if len(rows)!=len({x['external_id'] for x in rows}):raise SystemExit('live external_id duplicate')
 return rows
def main()->None:
 b=[r for r in read(B) if r['source_assertion']]; c=[r for r in read(C) if r['source_assertion']]
 if len(b)!=17 or len(c)!=17 or len({r['product_external_id'] for r in b+c})!=34:raise SystemExit('Wave219 exact-source lineage drift')
 candidates=[]
 for wave,rows in [('wave219b',b),('wave219c',c)]:
  for r in rows:
   model=r.get('model_token') or r.get('extracted_model') or ''
   # Only pre-existing official catalogues meet DescriptionSourceEvidencePolicy.
   catalogue=r['source_url'].casefold().endswith('.pdf'); blocked=r['product_external_id'] in STAGING_MODEL_CORE_HOLDS
   candidates.append({'wave':wave,'product_external_id':r['product_external_id'],'name':r['name'],'manufacturer':r['manufacturer_cluster'],'model_core':model,'source_url':r['source_url'],'source_snapshot_path':r['source_snapshot_path'],'source_snapshot_sha256':r['source_snapshot_sha256'],'source_kind':'official_manufacturer_catalogue' if catalogue else 'official_manufacturer_product_page','content_contract_eligible':'true' if catalogue and not blocked else 'false','partition':'catalogue_model_core_candidate' if catalogue and not blocked else 'hold_model_core_boundary' if blocked else 'hold_content_contract_requires_catalogue_source','hold_reason':STAGING_MODEL_CORE_HOLDS.get(r['product_external_id'],'') if blocked else '' if catalogue else 'pinned_official_product_page_is_not_a_supported_description_staging_source_kind','safe_to_stage':'false'})
 if Counter(x['wave'] for x in candidates)!={'wave219b':17,'wave219c':17}:raise SystemExit('wave counts drift')
 eligible=[x for x in candidates if x['content_contract_eligible']=='true']
 if len(eligible)!=15 or Counter(x['wave'] for x in eligible)!={'wave219b':2,'wave219c':13}:raise SystemExit('catalogue eligibility drift')
 db=live(); byid={x['external_id']:x for x in db}
 if set(x['product_external_id'] for x in candidates)-set(byid):raise SystemExit('candidate absent from live DB')
 guard=[]
 for x in candidates:
  item=byid[x['product_external_id']]
  if item['name']!=x['name']:raise SystemExit(f"live name drift: {x['product_external_id']}")
  peers=[]
  for other in db:
   if other['external_id']==x['product_external_id']:continue
   ids={norm(str(other.get(k) or '')) for k in ('mpn','sku','mpn_normalized','sku_normalized')}
   if norm(x['model_core']) in ids:peers.append(other['external_id'])
  guard.append({'product_external_id':x['product_external_id'],'model_core':x['model_core'],'live_identity_collision_ids':sorted(set(peers))})
 # Preserve the current visible name and structured identity: model_core only.
 manifest_rows=[]
 for x in eligible:
  technology='Герметизированная свинцово-кислотная аккумуляторная батарея' if x['manufacturer']=='Ventura' else 'Гелевая свинцово-кислотная аккумуляторная батарея'
  manifest_rows.append({'external_id':x['product_external_id'],'identity_scope':'model_core','manufacturer':x['manufacturer'],'model_core':x['model_core'],'technology':technology,'source_url':x['source_url'],'technical_attributes':{'Модель':x['model_core']},'source_kind':'official_manufacturer_catalogue','source_tier':'manufacturer_primary','source_publisher':'Ventura' if x['manufacturer']=='Ventura' else 'Exide Technologies','manufacturer_primary':True,'evidence_scope':'model_core','checked_at':'2026-07-29'})
 MANIFEST.write_text(json.dumps({'schema_version':1,'purpose':'Wave220 Russian source-backed description drafts only; model-core scope preserves catalogued identity.','locale':'ru-BY','products':manifest_rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 LIVE.write_text(json.dumps({'schema_version':1,'mode':'read_only','candidate_rows_checked':34,'checks':guard,'database_mutations':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 # The receipt is created by the separately invoked Laravel dry-run, then
 # this final rendering validates it so the summary cannot claim a dry-run
 # that differs from the exact manifest bytes.
 dry_ok=False
 if DRY.is_file():
  d=json.loads(DRY.read_text(encoding='utf-8-sig'));dry_ok=all((d.get('mode')=='dry_run',d.get('exit_code')==0,d.get('records')==len(manifest_rows),d.get('manifest_sha256')==sha(MANIFEST),d.get('database_mutations')==0,d.get('identity_fields_changed')==0,d.get('commercial_fields_changed')==0,d.get('publication_fields_changed')==0,d.get('url_mutations')==0))
 for x in candidates:
  if x['content_contract_eligible']=='true':x['safe_to_stage']='true' if dry_ok else 'false';x['partition']='stage_dry_run_verified' if dry_ok else 'catalogue_model_core_candidate';x['hold_reason']='' if dry_ok else 'awaiting_matching_laravel_dry_run_receipt'
 with OUT.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(candidates)
 summary={'schema_version':1,'batch':'wave220_description_enrichment','inputs':{B.name:{'sha256':sha(B),'source_proven_rows':17},C.name:{'sha256':sha(C),'source_proven_rows':17}},'source_proven_rows':34,'content_contract':{'catalogue_model_core_candidates':15,'held_official_product_pages':16,'held_model_core_boundary':3,'identity_scope':'model_core','identity_changes_proposed':0},'live_collision_guard':{'path':LIVE.relative_to(ROOT).as_posix(),'sha256':sha(LIVE),'rows_checked':34,'database_mutations':0},'manifest':{'path':MANIFEST.relative_to(ROOT).as_posix(),'sha256':sha(MANIFEST),'rows':15,'laravel_stage_dry_run_verified':dry_ok},'output':{'path':OUT.relative_to(ROOT).as_posix(),'sha256':sha(OUT),'rows':34},'policy':{'price_changes':0,'stock_changes':0,'media_changes':0,'identity_changes':0,'publication_changes':0,'apply_performed':False}}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave220 source-backed Russian description enrichment\n\nWave220 evaluates all 34 exact-source rows from Wave219-B (17) and Wave219-C (17). The existing content-staging policy accepts only SHA-pinned official manufacturer catalogues under model-core scope. Therefore 15 catalogue-backed rows (two Sonnenschein and thirteen Ventura) are description-draft candidates; 16 official product-page rows are explicitly held rather than being mislabelled as catalogues. Three Ventura rows are also held because their legacy `W` suffixes (`HRL12650W`, `HR1290W`, `HRL12155W`) do not pass the strict exact model-core boundaries of their pinned catalogue models.\n\nEvery manifest row preserves its current name and structured manufacturer/MPN by using `identity_scope: model_core`. Claims are limited to the exact model and battery technology supported by its pinned catalogue. Live identity checks are read only. Laravel stages the drafts only in a rolled-back dry run; no price, stock, media, identity, publication, or URL change is requested.\n',encoding='utf-8')
 print(json.dumps({'source_proven':34,'catalogue_candidates':15,'dry_run_verified':dry_ok},ensure_ascii=False))
if __name__=='__main__':main()
