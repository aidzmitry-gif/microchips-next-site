#!/usr/bin/env python3
"""Review the frozen ten-row EnerSys/Cyclon OCR slice without DB mutation."""
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]; TMP=ROOT/'.tmp/wave232-ocr'; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'; SRC=ROOT/'docs/audits/sources/wave209a'
INPUTS=(TMP/'wave227-ocr-input-001.csv',TMP/'wave227-ocr-input-002.csv'); EVIDENCE=GEN/'rb-wave209a-official-evidence.csv'; REGISTRY=GEN/'rb-wave209a-official-source-registry.json'; PDF=SRC/'enersys-cyclon-selection-guide.pdf'
MANIFEST=IMP/'rb-reviewed-legacy-preview-media-wave232e-2026-07-29.json'; LEDGER=GEN/'rb-wave232e-enersys-cyclon-media-review.csv'; SUMMARY=GEN/'rb-wave232e-enersys-cyclon-media-review.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave232e-enersys-cyclon-media-review.md'
PINS={INPUTS[0]:'2193d5dfb409ab556fdd3cd7bfa196cd7f7ff7e0502b55f61e95e85ece8ee170',INPUTS[1]:'8dba62e2c8926f419762ed5d089052d7fc77ce7f039f2a9b6fddac37bb32a7bb',EVIDENCE:'5d093d66deddc3ad25858e918ccf1fa72a9087f78db42785632e8af5ffe62aa9',REGISTRY:'bc34c9169aa88bec5771ef02722e01cd666b50e778bbe75fae2646b6ca380149',PDF:'3c6ecbb7f5379fccd8c2f5e31b999ac6f4d62117377b56b5f1e9df578e8fec5f'}
EXPECTED={'bitrix:24526':'0810-0011','bitrix:24527':'0810-0077','bitrix:24533':'0850-0102','bitrix:24534':'0850-0103','bitrix:24535':'0860-0102','bitrix:24551':'0810-0008','bitrix:24552':'0810-0016','bitrix:24553':'0810-0067','bitrix:24577':'0819-0030','bitrix:24582':'0859-0016'}
HOLDS={'bitrix:24526':'no_complete_model_label_visible','bitrix:24527':'no_complete_model_label_visible','bitrix:24533':'model_label_not_legible_at_source_resolution','bitrix:24534':'model_label_not_legible_at_source_resolution','bitrix:24535':'model_label_not_legible_at_source_resolution','bitrix:24551':'visible_label_not_provably_expected_mpn','bitrix:24552':'no_complete_model_label_visible','bitrix:24553':'no_complete_model_label_visible','bitrix:24577':'model_label_not_legible_at_source_resolution'}
FIELDS=('external_id','media_id','expected_mpn','official_catalogue_exact_mpn','asset_sha256','visual_decision','visible_mpn','reason','rights_basis','identity_proof','media_rights_scope')
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def req(ok:bool,msg:str)->None:
 if not ok:raise SystemExit(msg)
def rows(p:Path):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def norm(v:str)->str:return ''.join(c for c in v.upper() if c.isalnum())
def build():
 for p,h in PINS.items():req(sha(p)==h,f'pin drift: {p.relative_to(ROOT)}')
 selected=[r for p in INPUTS for r in rows(p) if r['external_id'] in EXPECTED]
 req(len(selected)==10 and {r['external_id'] for r in selected}==set(EXPECTED), 'frozen EnerSys/Cyclon scope drift')
 req(all(r['expected_mpn']==EXPECTED[r['external_id']] for r in selected),'expected MPN drift')
 evidence={r['product_external_id']:r for r in rows(EVIDENCE)}; registry={r['filename']:r for r in json.loads(REGISTRY.read_text(encoding='utf-8'))}; source=registry['enersys-cyclon-selection-guide.pdf']
 req(source['sha256']==sha(PDF),'EnerSys registry/PDF drift'); official=norm('\n'.join(x.extract_text() or '' for x in PdfReader(PDF).pages))
 ledger=[]; passed=[]
 for r in selected:
  ext,mpn=r['external_id'],r['expected_mpn']; path=Path(r['image_path']); ev=evidence.get(ext)
  req(path.is_file() and sha(path)==r['hash'],'company-owned asset hash drift: '+ext)
  req(ev is not None and ev['partition']=='exact_safe' and ev['model_token']==mpn and ev['source_snapshot_sha256']==source['sha256'] and norm(mpn) in official,'official identity evidence drift: '+ext)
  passed_exact=ext=='bitrix:24582'; visible=mpn if passed_exact else ''
  decision='PASS' if passed_exact else 'HOLD'; reason='visible_complete_exact_mpn_on_company_owned_asset' if passed_exact else HOLDS[ext]
  ledger.append({'external_id':ext,'media_id':r['media_id'],'expected_mpn':mpn,'official_catalogue_exact_mpn':'true','asset_sha256':r['hash'],'visual_decision':decision,'visible_mpn':visible,'reason':reason,'rights_basis':'Company-owned Microchips legacy Bitrix upload backup.','identity_proof':'official_EnerSys_Cyclon_catalogue_exact_part_number','media_rights_scope':'company_owned_legacy_asset_only'})
  if passed_exact: passed.append({'external_id':ext,'media_id':int(r['media_id']),'content_sha256':r['hash'],'storage_path':'legacy-staging/rb/'+path.name,'rights_basis':'Company-owned Microchips legacy Bitrix upload backup.','identity_scope':'exact','mpn':mpn,'identity_evidence_level':'visible_exact_mpn','visual_verification_note':'Manual visual review: complete visible label 0859-0016 agrees with SHA-pinned official EnerSys Cyclon catalogue.','reviewed_at':'2026-07-29'})
 req(len(passed)==1 and passed[0]['external_id']=='bitrix:24582','PASS safety drift')
 with LEDGER.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=FIELDS,lineterminator='\n');w.writeheader();w.writerows(ledger)
 manifest={'schema_version':1,'purpose':'Promote only Wave232-E company-owned EnerSys/Cyclon assets with a complete visually exact MPN and independent official-catalogue identity proof.','locale':'ru-BY','images':passed};MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 summary={'schema_version':1,'wave':'wave232e_enersys_cyclon_media_review','inputs':{p.relative_to(ROOT).as_posix():sha(p) for p in PINS},'coverage':{'frozen_candidates':10,'official_exact_identity_proofs':10,'pass_visible_exact_mpn':1,'holds':9},'manifest':{'path':MANIFEST.relative_to(ROOT).as_posix(),'sha256':sha(MANIFEST),'rows':1},'ledger':{'path':LEDGER.relative_to(ROOT).as_posix(),'sha256':sha(LEDGER),'rows':10},'safety':{'database_operations':0,'apply_performed':False,'media_changes':0,'publication_changes':0,'third_party_image_rights_claimed':False}};SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text('# Wave232-E: EnerSys/Cyclon media identity review\n\nExactly ten 0810/0850/0860/0819/0859 candidates from the frozen Wave227 OCR inputs 001 and 002 were reviewed. All ten expected part numbers are independently present in the SHA-pinned official EnerSys Cyclon selection-guide, which is used only as identity proof. It is not a licence to copy a manufacturer image.\n\nOnly `bitrix:24582` passes: its company-owned Bitrix asset visibly and completely shows `0859-0016`, matching the official catalogue. The other nine images do not expose a complete, readable expected MPN or package proof at their original resolution and remain HOLD. The manifest therefore contains one image only; the ledger retains all ten decisions. No DB or media change was performed.\n',encoding='utf-8');return summary
if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False))
