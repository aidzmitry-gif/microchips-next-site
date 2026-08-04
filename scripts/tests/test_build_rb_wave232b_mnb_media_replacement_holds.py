from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/build-rb-wave232b-mnb-media-replacement-holds.py'; HOLDS=ROOT/'docs/audits/generated/rb-wave232b-mnb-media-replacement-holds.csv'; SUMMARY=ROOT/'docs/audits/generated/rb-wave232b-mnb-media-replacement-holds.summary.json'; REPORT=ROOT/'docs/audits/2026-07-29-rb-wave232b-mnb-media-replacement-holds.md'
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def test_wave232b_fails_closed_without_visible_company_owned_candidate()->None:
 subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True); first=tuple(sha(p) for p in (HOLDS,SUMMARY,REPORT)); subprocess.run([sys.executable,str(SCRIPT)],cwd=ROOT,check=True,capture_output=True); assert first==tuple(sha(p) for p in (HOLDS,SUMMARY,REPORT))
 with HOLDS.open(encoding='utf-8-sig',newline='') as h: rows=list(csv.DictReader(h))
 summary=json.loads(SUMMARY.read_text(encoding='utf-8')); assert {r['external_id'] for r in rows}=={'bitrix:2909','bitrix:3056'}; assert all(r['exact_company_owned_candidate_found']=='false' and r['duplicate_backup_file_materialized']=='false' and r['official_model_confirmed']=='true' for r in rows); assert summary['coverage']=={'targets':2,'exact_company_owned_candidates':0,'holds':2,'exact_media_manifest_emitted':False}; assert summary['safety']['database_operations']==0
