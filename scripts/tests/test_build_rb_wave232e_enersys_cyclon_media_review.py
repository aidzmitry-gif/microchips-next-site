from __future__ import annotations
import csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SCRIPT=ROOT/'scripts/build-rb-wave232e-enersys-cyclon-media-review.py';M=ROOT/'docs/imports/rb-reviewed-legacy-preview-media-wave232e-2026-07-29.json';L=ROOT/'docs/audits/generated/rb-wave232e-enersys-cyclon-media-review.csv';S=ROOT/'docs/audits/generated/rb-wave232e-enersys-cyclon-media-review.summary.json';R=ROOT/'docs/audits/2026-07-29-rb-wave232e-enersys-cyclon-media-review.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def test_wave232e_is_deterministic_and_promotes_only_visually_exact_asset():
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True); first=tuple(sha(p) for p in (M,L,S,R));subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True);assert first==tuple(sha(p) for p in (M,L,S,R))
 manifest=json.loads(M.read_text(encoding='utf-8')); summary=json.loads(S.read_text(encoding='utf-8'))
 with L.open(encoding='utf-8-sig',newline='') as h: ledger=list(csv.DictReader(h))
 assert len(ledger)==10 and len(manifest['images'])==1 and manifest['images'][0]['external_id']=='bitrix:24582' and manifest['images'][0]['mpn']=='0859-0016'
 assert set(manifest['images'][0]) == {'external_id','media_id','content_sha256','storage_path','rights_basis','identity_scope','mpn','identity_evidence_level','visual_verification_note','reviewed_at'}
 assert manifest['images'][0]['reviewed_at']=='2026-07-29'
 assert sum(x['visual_decision']=='HOLD' for x in ledger)==9;assert summary['coverage']=={'frozen_candidates':10,'official_exact_identity_proofs':10,'pass_visible_exact_mpn':1,'holds':9};assert summary['safety']['database_operations']==0
