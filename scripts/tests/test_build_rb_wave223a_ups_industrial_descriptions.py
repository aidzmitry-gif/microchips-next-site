import csv,json
import importlib.util
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; GEN=ROOT/'docs/audits/generated'; IMP=ROOT/'docs/imports'
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def test_wave223a_scope_is_exactly_the_canonical_queue():
 ledger=rows(GEN/'rb-wave223a-ups-industrial-description-ledger.csv'); summary=json.loads((GEN/'rb-wave223a-ups-industrial-description.summary.json').read_text(encoding='utf-8'))
 canonical=rows(GEN/'rb-enrichment-queue-wave223c-a-ups-industrial.csv')
 assert len(ledger)==len({x['product_external_id'] for x in ledger})==300
 assert [x['product_external_id'] for x in ledger]==[x['product_external_id'] for x in canonical]
 assert {x['category_external_id'] for x in ledger}<={'seo:batteries-ups','seo:batteries-industrial'}
 assert summary['input']['canonical_all_rows_used'] is True and summary['selection']['first_input_priority']=='4' and summary['selection']['last_input_priority']=='428'
def test_wave223a_selection_is_deterministic_from_pinned_inputs():
 spec=importlib.util.spec_from_file_location('wave223a',ROOT/'scripts/build-rb-wave223a-ups-industrial-descriptions.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
 queue=mod.read_csv(mod.INPUT); first=mod.select(queue); second=mod.select(queue)
 assert [x['product_external_id'] for x in first]==[x['product_external_id'] for x in second]
 assert len(first)==300 and [x['priority'] for x in first][:3]==['4','5','6']
def test_wave223a_candidates_are_primary_source_bounded_and_all_other_rows_hold():
 ledger=rows(GEN/'rb-wave223a-ups-industrial-description-ledger.csv'); manifest=json.loads((IMP/'rb-source-backed-description-candidates-wave223a-2026-07-29.json').read_text(encoding='utf-8'))
 candidates=[x for x in ledger if x['partition']=='source_backed_description_candidate']
 assert len(candidates)==len(manifest['products'])==40
 assert all(x['safe_to_stage']=='false' and x['source_url'].startswith('https://') and x['description_ru'] for x in candidates)
 assert Counter(x['manufacturer'] for x in manifest['products'])=={'CSB':22,'EnerSys':18}
 assert all(x['local_evidence_path'].startswith('docs/imports/rb-source-backed-description-drafts-') and len(x['local_evidence_sha256'])==64 for x in manifest['products'])
 assert all(x['partition']=='hold_no_source_backed_description' and not x['description_ru'] and x['hold_reason'] for x in ledger if x not in candidates)
 assert all(x['safe_to_stage'] is False and x['content_scope']=='exact_model_and_technology_only' for x in manifest['products'])
