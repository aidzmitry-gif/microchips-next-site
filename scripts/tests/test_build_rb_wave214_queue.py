import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"

def ids(name):
    with (GEN / name).open(encoding="utf-8-sig", newline="") as f: return [row["product_external_id"] for row in csv.DictReader(f)]

def test_wave214_no_repeat_and_deterministic():
    result = json.loads((GEN / "rb-b2b-wave214.verification.json").read_text(encoding="utf-8"))
    register, queue, batch = ids("rb-b2b-processed-register-wave214.csv"), ids("rb-b2b-priority-queue-wave214.csv"), ids("rb-b2b-next-source-batch-wave214.csv")
    assert len(register) == len(set(register)) == 2500
    assert len(queue) == len(set(queue)) == len(batch) == len(set(batch)) == 500
    assert not set(register) & set(queue) and set(queue) == set(batch)
    assert all(result["byte_identical_rerun"].values())

def test_wave214_scope_and_side_effect_gates():
    result = json.loads((GEN / "rb-b2b-wave214.verification.json").read_text(encoding="utf-8"))
    assert result["priority"]["overlap_with_processed_register"] == result["source_planner"]["overlap_with_processed_register"] == 0
    assert result["source_planner"]["automotive_excluded"] == result["source_planner"]["electronics_excluded"] == 0
    assert result["safe_to_apply_records"] == 0
    assert result["automatic_web_requests"] == result["automatic_database_queries"] == result["automatic_database_mutations"] == 0
