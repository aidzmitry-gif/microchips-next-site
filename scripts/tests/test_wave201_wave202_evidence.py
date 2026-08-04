import csv, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_wave201_no_repeat_evidence_is_complete_and_fail_closed():
    with (ROOT/"docs/audits/generated/rb-wave201-cameron-sino-no-repeat-evidence.csv").open(encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    summary=json.loads((ROOT/"docs/audits/generated/rb-wave201-cameron-sino-no-repeat-summary.json").read_text(encoding="utf-8"))
    assert len(rows)==12 and len({r['product_external_id'] for r in rows})==12
    assert all(r['safe_to_apply']=='false' and r['prior_wave99_100_overlap']=='false' for r in rows)
    assert summary['manufacturer_primary_drafts']==summary['media_records']==summary['current_price_evidence_records']==0
def test_wave202_builder_keeps_unknown_oem_labels_fail_closed(tmp_path):
    spec=importlib.util.spec_from_file_location('w202',ROOT/'scripts/build-rb-wave202-honeywell-evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=tmp_path/'in.csv'; source.write_text('batch,product_external_id,name\n'+'\n'.join(f'honeywell_mobile_computers,bitrix:{i},Battery for Honeywell {i}' for i in range(42)),encoding='utf-8-sig')
    assert m.build(source,tmp_path)['classification_counts']['no_evidence']==42
    with (tmp_path/'rb-wave202-honeywell-evidence.csv').open(encoding='utf-8-sig') as f: assert all(r['safe_to_apply']=='false' for r in csv.DictReader(f))

def test_wave202_registry_marks_prior_wave174_as_processed_not_new_evidence():
    with (ROOT/'docs/audits/generated/rb-wave202-honeywell-evidence.csv').open(encoding='utf-8-sig', newline='') as f: rows=list(csv.DictReader(f))
    prior=[r for r in rows if r['classification']=='previously_processed']
    assert {r['product_external_id'] for r in prior}=={'bitrix:12116','bitrix:12258','bitrix:12270'}
    assert all(r['no_repeat_prior_artifact']=='wave174_exact' and r['source_url'].startswith('https://prod-edam.honeywell.com/') for r in prior)
