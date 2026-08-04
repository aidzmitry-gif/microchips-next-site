#!/usr/bin/env python3
"""Fail-closed Exide/Sonnenschein descriptions for new Wave227 media rows only."""
from __future__ import annotations
import csv,hashlib,json,re,unicodedata
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
MEDIA=GEN/'rb-reviewed-legacy-preview-media-wave227.csv'; READY=GEN/'rb-full-content-readiness-wave227-after.csv'; PRIOR=GEN/'rb-wave211c-stationary-evidence.csv'; REG=ROOT/'docs/audits/sources/wave211c-stationary/source-registry.json'
LEDGER=GEN/'rb-wave228a-sonnenschein-description-ledger.csv'; EVIDENCE=IMP/'rb-source-backed-description-evidence-wave228a-2026-07-29.json'; STAGE=IMP/'rb-source-backed-description-stage-manifest-wave228a-2026-07-29.json'; SUMMARY=GEN/'rb-wave228a-sonnenschein-description.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave228a-sonnenschein-descriptions.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def norm(v):return re.sub(r'[^A-Z0-9]','',unicodedata.normalize('NFKC',v or '').upper())
def key(m):return 'exide-sonnenschein-a400.pdf' if m.startswith('A4') else 'exide-sonnenschein-a500.pdf' if m.startswith('A5') else 'exide-sonnenschein-a700.pdf' if m.startswith('A7') else 'exide-sonnenschein-a600.pdf'
def main():
 ready={x['product_external_id']:x for x in rows(READY)}; target=[x for x in rows(MEDIA) if x['external_id'] in ready and ready[x['external_id']]['manufacturer']=='Sonnenschein' and ready[x['external_id']]['has_applied_description']=='false']
 if len(target)!=28 or len({x['external_id'] for x in target})!=28:raise SystemExit('Wave227 Sonnenschein scope drift')
 prior_rows={x['product_external_id']:x for x in rows(PRIOR) if x['partition']=='exact_safe'}; registry={x['source_id']:x for x in json.loads(REG.read_text(encoding='utf-8-sig'))['sources']}
 texts={};pins={}
 for k in set(key(x['expected_mpn']) for x in target):
  s=registry[k];p=ROOT/s['snapshot_path']
  if not p.is_file() or sha(p)!=s['snapshot_sha256'] or 'exidegroup.com' not in s['source_url']:raise SystemExit('Exide pin drift')
  texts[k]=norm('\n'.join(page.extract_text() or '' for page in PdfReader(p).pages));pins[k]=s
 ledger=[];stage=[];evidence=[]
 for x in target:
  eid,m=x['external_id'],x['expected_mpn'];s=pins[key(m)];exact=norm(m) in texts[key(m)]
  reused=prior_rows.get(eid); part='stageable_reused_wave211c_source' if reused else ('stageable_exact_source' if exact else 'hold_exact_model_absent_from_pinned_official_source')
  src={'source_url':reused['source_url'],'snapshot_path':reused['source_snapshot_path'].replace('../audits/','docs/audits/'),'snapshot_sha256':reused['source_snapshot_sha256'],'publisher':reused['source_publisher']} if reused else {'source_url':s['source_url'],'snapshot_path':s['snapshot_path'],'snapshot_sha256':s['snapshot_sha256'],'publisher':s['publisher']}
  row={'external_id':eid,'media_id':x['media_id'],'manufacturer':'Sonnenschein','mpn':m,'partition':part,'source_url':src['source_url'] if part.startswith('stageable') else '','snapshot_path':src['snapshot_path'] if part.startswith('stageable') else '','snapshot_sha256':src['snapshot_sha256'] if part.startswith('stageable') else '','hold_reason':'' if part.startswith('stageable') else 'exact_model_absent_from_pinned_official_source'};ledger.append(row)
  if part.startswith('stageable'):
   e={'external_id':eid,'manufacturer':'Sonnenschein','model_core':m,'technology':'GEL','source_url':src['source_url'],'technical_attributes':{'Модель':m},'source_kind':'official_manufacturer_catalogue','source_tier':'manufacturer_primary','source_publisher':src['publisher'],'manufacturer_primary':True,'evidence_scope':'model_core','identity_scope':'model_core','checked_at':'2026-07-29'};stage.append(e);evidence.append({**e,'source_snapshot_path':src['snapshot_path'],'source_snapshot_sha256':src['snapshot_sha256']})
 fields=list(ledger[0]);
 with LEDGER.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(ledger)
 EVIDENCE.write_text(json.dumps({'schema_version':1,'purpose':'Wave228-A evidence only; excludes already researched Wave211-C IDs.','products':evidence},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 STAGE.write_text(json.dumps({'schema_version':1,'purpose':'Wave228-A source-backed description drafts; stage only after review.','locale':'ru-BY','products':stage},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 summary={'schema_version':1,'target_rows':28,'reused_wave211c_official_source_rows':sum(x['partition']=='stageable_reused_wave211c_source' for x in ledger),'new_exact_source_rows':sum(x['partition']=='stageable_exact_source' for x in ledger),'stageable_exact_source_rows':len(stage),'official_source_absent_holds':sum(x['partition']=='hold_exact_model_absent_from_pinned_official_source' for x in ledger),'source_registry':{k:{'path':v['snapshot_path'],'sha256':v['snapshot_sha256']} for k,v in pins.items()},'stage_contract':{'refresh_existing_required':True,'refresh_applied_required':True,'legacy_evidence_upgrade_only':True},'database_apply':False,'commit_or_push':False};SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave228-A Sonnenschein descriptions\n\nSelected exactly 28 Wave227 verified-media Sonnenschein products with `legacy_preview_applied` drafts. Eighteen exact models reuse their already pinned Wave211-C Exide evidence without repeating research; ten additional exact MPNs are checked against the same SHA-pinned official Exide/Sonnenschein catalogues. All 28 form a conservative model-core manifest intended only for `--refresh-existing --refresh-applied` legacy-evidence upgrades. Attributes contain only the exact model and GEL technology. No DB apply occurred.\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
