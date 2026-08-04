#!/usr/bin/env python3
"""Materialize the canonical Wave223-A evidence into a future-stageable manifest.

No Laravel command is invoked here: the requested manufacturer product-page
policy pair is intentionally pending the root policy extension.
"""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
QUEUE=GEN/'rb-enrichment-queue-wave223c-a-ups-industrial.csv'; EVIDENCE=IMP/'rb-source-backed-description-candidates-wave223a-2026-07-29.json'
OUT=IMP/'rb-source-backed-description-stage-manifest-wave224a-2026-07-29.json'; SUMMARY=GEN/'rb-wave224a-description-stage-manifest.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave224a-description-stage-manifest.md'
ALLOWED={'external_id','identity_scope','manufacturer','model_core','technology','source_url','technical_attributes','source_kind','source_tier','source_publisher','manufacturer_primary','evidence_scope','checked_at'}
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p:Path)->list[dict[str,str]]:
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def main()->None:
 queue={r['product_external_id']:r for r in rows(QUEUE)}
 if len(queue)!=300: raise SystemExit('canonical queue drift')
 evidence=json.loads(EVIDENCE.read_text(encoding='utf-8-sig'))
 candidates=evidence.get('products')
 if not isinstance(candidates,list) or len(candidates)!=40 or len({r.get('external_id') for r in candidates})!=40: raise SystemExit('Wave223-A candidate scope drift')
 products=[]; registry={}
 for r in candidates:
  eid=r.get('external_id'); current=queue.get(eid)
  if not current or r.get('model')!=current['mpn'] or r.get('current_name')!=current['name'] or r.get('manufacturer','').casefold()!=current['manufacturer'].casefold():
   raise SystemExit(f'current external-id/model-core drift: {eid}')
  path=r.get('local_evidence_path',''); pin=ROOT/path
  if not path or not pin.is_file() or sha(pin)!=r.get('local_evidence_sha256'):
   raise SystemExit(f'local evidence pin drift: {eid}')
  technology=(r.get('verified_facts') or {}).get('technology')
  if not isinstance(technology,str) or not technology.strip() or not isinstance(r.get('source_url'),str) or not r['source_url'].startswith('https://'):
   raise SystemExit(f'incomplete source facts: {eid}')
  row={'external_id':eid,'identity_scope':'model_core','manufacturer':r['manufacturer'],'model_core':r['model'],'technology':technology.strip(),'source_url':r['source_url'],'technical_attributes':{'Технология':technology.strip()},'source_kind':'official_manufacturer_product_page','source_tier':'manufacturer_primary','source_publisher':r['source_publisher'],'manufacturer_primary':True,'evidence_scope':'model_core','checked_at':r['checked_at']}
  if set(row)!=ALLOWED or not row['technical_attributes']: raise SystemExit(f'manifest shape drift: {eid}')
  products.append(row); registry[path]=r['local_evidence_sha256']
 manifest={'schema_version':1,'purpose':'Wave224-A source-backed description drafts only; materialization awaits product-page policy extension.','locale':'ru-BY','products':products}
 OUT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 summary={'schema_version':1,'batch':'wave224a_description_materialization','candidate_evidence':{'path':EVIDENCE.relative_to(ROOT).as_posix(),'sha256':sha(EVIDENCE),'rows':40},'canonical_queue':{'path':QUEUE.relative_to(ROOT).as_posix(),'sha256':sha(QUEUE),'rows':300},'scope':{'products':len(products),'external_ids':len({r['external_id'] for r in products}),'manufacturer_counts':dict(sorted(Counter(r['manufacturer'] for r in products).items())),'model_core_matches_current_queue':True},'pinned_source_registry':{'files':[{'path':p,'sha256':h} for p,h in sorted(registry.items())]},'manifest':{'path':OUT.relative_to(ROOT).as_posix(),'sha256':sha(OUT),'rows':len(products),'allowed_product_fields':sorted(ALLOWED)},'laravel_execution':{'invoked':False,'reason':'official_manufacturer_product_page/manufacturer_primary policy extension is pending'},'intent':{'price_changes':0,'stock_changes':0,'media_changes':0,'publication_changes':0,'url_changes':0,'identity_changes':0,'database_apply':False,'commit_or_push':False}}
 SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave224-A description materialization manifest\n\nA separate 40-row Laravel-stageable manifest was materialized from the canonical Wave223-A evidence. Every row has its current external ID and exact model core, a SHA-pinned local evidence registry entry, an HTTPS manufacturer source URL, publisher, date, and a non-empty technology attribute map.\n\n- Contract fields use `source_kind: official_manufacturer_product_page`, `source_tier: manufacturer_primary`, `identity_scope: model_core`, `evidence_scope: model_core`, and `manufacturer_primary: true`.\n- The original Wave223-A candidate manifest remains evidence-only and is not modified.\n- No Laravel command or DB operation was run: this source-kind/tier pair awaits the root policy extension. The manifest has no commercial, media, publication, URL, or identity-change intent.\n',encoding='utf-8')
 print(json.dumps({'rows':len(products),'laravel_invoked':False,'database_mutations':0}))
if __name__=='__main__':main()
