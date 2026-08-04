from __future__ import annotations
import csv, json, subprocess
from pathlib import Path

ROOT=Path(__file__).parents[2]
OUT=ROOT/"docs/audits/generated/wave202-oem-replacement-evidence.csv"
SUMMARY=ROOT/"docs/audits/generated/wave202-oem-replacement-evidence-summary.json"
def test_wave202_is_complete_and_fail_closed() -> None:
    rows=list(csv.DictReader(OUT.open(encoding="utf-8-sig")))
    assert len(rows)==44 and len({r['product_external_id'] for r in rows})==44
    assert {r['partition'] for r in rows} <= {'exact_safe','compatibility_only','conflict','no_evidence','previously_processed'}
    assert all(r['safe_to_apply']=='false' for r in rows)
def test_oem_compatibility_is_not_promoted_to_replacement_evidence() -> None:
    rows=list(csv.DictReader(OUT.open(encoding="utf-8-sig")))
    assert all(r['hold_reason'] for r in rows)
    assert sum(r['partition']=='previously_processed' for r in rows)==1
    data=json.loads(SUMMARY.read_text(encoding='utf-8'))
    assert data['exact_safe_records']==0 and data['automatic_database_mutations']==0
