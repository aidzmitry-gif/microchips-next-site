import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
VERIFY = GEN / "rb-b2b-wave212.verification.json"

def ids(name):
    with (GEN / name).open(encoding="utf-8-sig", newline="") as f:
        return [r["product_external_id"] for r in csv.DictReader(f)]

def test_wave212_is_no_repeat_and_deterministic():
    result = json.loads(VERIFY.read_text(encoding="utf-8"))
    register, queue, batch = ids("rb-b2b-processed-register-wave212.csv"), ids("rb-b2b-priority-queue-wave212.csv"), ids("rb-b2b-next-source-batch-wave212.csv")
    assert len(register) == len(set(register)) == 2000
    assert len(queue) == len(set(queue)) == len(batch) == len(set(batch)) == 500
    assert not set(register) & set(queue)
    assert set(queue) == set(batch)
    assert all(result["byte_identical_rerun"].values())

def test_wave212_exclusions_and_no_side_effects():
    result = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert result["priority"]["overlap_with_processed_register"] == 0
    assert result["source_planner"]["overlap_with_processed_register"] == 0
    assert result["source_planner"]["automotive_excluded"] == result["source_planner"]["electronics_excluded"] == 0
    assert result["safe_to_apply_records"] == 0
    assert result["automatic_web_requests"] == result["automatic_database_queries"] == result["automatic_database_mutations"] == 0
