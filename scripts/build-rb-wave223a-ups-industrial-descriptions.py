#!/usr/bin/env python3
"""Build a fail-closed source-backed description queue for UPS/industrial batteries.

This is a research artifact, not a staging or import command. Only the
canonical Wave223-C A queue and already pinned local manufacturer evidence are
used; all other rows are held rather than filled from titles or reseller material.
"""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
INPUT=GEN/'rb-enrichment-queue-wave223c-a-ups-industrial.csv'
SOURCES=[IMP/'rb-source-backed-description-drafts-csb-wave178-2026-07-29.json',IMP/'rb-source-backed-description-drafts-enersys-wave187-2026-07-29.json']
OUT=GEN/'rb-wave223a-ups-industrial-description-ledger.csv'; CANDIDATES=IMP/'rb-source-backed-description-candidates-wave223a-2026-07-29.json'; SUMMARY=GEN/'rb-wave223a-ups-industrial-description.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave223a-ups-industrial-descriptions.md'
ALLOWED={'seo:batteries-ups','seo:batteries-industrial'}
FIELDS=['selection_rank','input_priority','product_external_id','name','manufacturer','mpn','category_external_id','partition','source_url','source_snapshot_path','source_snapshot_sha256','source_publisher','verified_voltage_v','verified_capacity_ah','description_ru','hold_reason','safe_to_stage']
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def read_csv(p:Path)->list[dict[str,str]]:
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def source_index()->dict[str,dict[str,str]]:
 index={}
 for p in SOURCES:
  source=json.loads(p.read_text(encoding='utf-8-sig'))
  for r in source['products']:
   if not all(r.get(k) for k in ('external_id','manufacturer','mpn','source_url','technology')) or not r['source_url'].startswith('https://'):
    raise SystemExit(f'incomplete pinned evidence: {p.name}')
   if r['external_id'] in index and index[r['external_id']]!=r: raise SystemExit(f'conflicting exact source: {r["external_id"]}')
   index[r['external_id']]={**r,'local_evidence_path':p.relative_to(ROOT).as_posix(),'local_evidence_sha256':sha(p)}
 return index
def select(rows:list[dict[str,str]])->list[dict[str,str]]:
 if len(rows)!=300 or len({r['product_external_id'] for r in rows})!=300 or set(r['category_external_id'] for r in rows)-ALLOWED:
  raise SystemExit('canonical Wave223-C A scope drift')
 return rows
def prose(manufacturer:str, model:str, technology:str)->str:
 return f'Аккумулятор {manufacturer} {model}. Согласно закреплённому источниковому описанию производителя, технология — {technology}.'
def main()->None:
 queue=read_csv(INPUT); selected=select(queue)
 sources=source_index(); ledger=[]; candidates=[]
 for rank,r in enumerate(selected,1):
  source=sources.get(r['product_external_id'])
  if source and source['mpn']==r['mpn'] and source['manufacturer'].casefold()==r['manufacturer'].casefold():
   text=prose(source['manufacturer'],source['mpn'],source['technology'])
   row={'selection_rank':rank,'input_priority':r['priority'],'product_external_id':r['product_external_id'],'name':r['name'],'manufacturer':r['manufacturer'],'mpn':r['mpn'],'category_external_id':r['category_external_id'],'partition':'source_backed_description_candidate','source_url':source['source_url'],'source_snapshot_path':source['local_evidence_path'],'source_snapshot_sha256':source['local_evidence_sha256'],'source_publisher':source['manufacturer'],'verified_voltage_v':'','verified_capacity_ah':'','description_ru':text,'hold_reason':'','safe_to_stage':'false'}
   candidates.append({'external_id':r['product_external_id'],'current_name':r['name'],'manufacturer':source['manufacturer'],'model':source['mpn'],'description_ru':text,'source_url':source['source_url'],'source_kind':'official_manufacturer_catalogue' if source['source_url'].endswith('.pdf') else 'official_manufacturer_product_page','source_tier':'manufacturer_primary','source_publisher':source['manufacturer'],'local_evidence_path':source['local_evidence_path'],'local_evidence_sha256':source['local_evidence_sha256'],'verified_facts':{'technology':source['technology']},'identity_scope':'existing_queue_mpn_only','content_scope':'exact_model_and_technology_only','checked_at':'2026-07-29','safe_to_stage':False})
  else:
   reason='no_pinned_primary_exact_model_source_in_local_evidence' if not source else 'queue_identity_does_not_equal_pinned_exact_source_model'
   row={'selection_rank':rank,'input_priority':r['priority'],'product_external_id':r['product_external_id'],'name':r['name'],'manufacturer':r['manufacturer'],'mpn':r['mpn'],'category_external_id':r['category_external_id'],'partition':'hold_no_source_backed_description','source_url':'','source_snapshot_path':'','source_snapshot_sha256':'','source_publisher':'','verified_voltage_v':'','verified_capacity_ah':'','description_ru':'','hold_reason':reason,'safe_to_stage':'false'}
  ledger.append(row)
 with OUT.open('w',encoding='utf-8-sig',newline='') as h:
  w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(ledger)
 CANDIDATES.write_text(json.dumps({'schema_version':1,'purpose':'Wave223-A source-backed description candidates only; no staging, publication, price, stock, identity, URL or media changes.','locale':'ru-BY','products':candidates},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 summary={'schema_version':1,'batch':'wave223a_ups_industrial_descriptions','input':{'path':INPUT.relative_to(ROOT).as_posix(),'sha256':sha(INPUT),'rows':len(queue),'canonical_all_rows_used':True},'selection':{'rows':len(selected),'unique_external_ids':len({r['product_external_id'] for r in selected}),'category_counts':dict(sorted(Counter(r['category_external_id'] for r in selected).items())),'first_input_priority':selected[0]['priority'],'last_input_priority':selected[-1]['priority']},'pinned_source_registry':{'files':[{ 'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in SOURCES],'exact_primary_models':len(sources)},'partition_counts':dict(sorted(Counter(r['partition'] for r in ledger).items())),'description_candidates':{'path':CANDIDATES.relative_to(ROOT).as_posix(),'sha256':sha(CANDIDATES),'rows':len(candidates),'safe_to_stage_rows':0},'hold_ledger':{'path':OUT.relative_to(ROOT).as_posix(),'sha256':sha(OUT),'rows':len(ledger)},'policy':{'network_downloads':0,'third_party_image_copies':0,'price_changes':0,'stock_changes':0,'database_apply':False,'publication_changes':0,'commit_or_push':False}}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave223-A UPS and industrial-battery description research\n\nUses exactly all 300 rows of the canonical `rb-enrichment-queue-wave223c-a-ups-industrial.csv` queue; no rows from the superseded Wave222 selection are included.\n\n- '+str(len(candidates))+' rows have concise Russian description candidates from already pinned CSB or EnerSys manufacturer evidence. Each draft states only the exact model and technology recorded in that evidence.\n- '+str(len(ledger)-len(candidates))+' rows are held: title/MPN fields and non-primary material are not enough to create prose.\n- This is research only: no staging, DB apply, publication, price/stock/identity/URL/media change, network download or image copy occurred.\n',encoding='utf-8')
 print(json.dumps({'selected':len(selected),'candidates':len(candidates),'holds':len(ledger)-len(candidates),'database_mutations':0},ensure_ascii=False))
if __name__=='__main__':main()
