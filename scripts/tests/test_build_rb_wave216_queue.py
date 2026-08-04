import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"


def ids(name):
    with (GEN / name).open(encoding="utf-8-sig", newline="") as handle:
        return [row["product_external_id"] for row in csv.DictReader(handle)]


def test_wave216_exact_processed_lineage_and_no_repeat_queue():
    verify = json.loads((GEN / "rb-b2b-wave216.verification.json").read_text(encoding="utf-8"))
    register = ids("rb-b2b-processed-register-wave216.csv")
    queue = ids("rb-b2b-priority-queue-wave216.csv")
    batch = ids("rb-b2b-next-source-batch-wave216.csv")
    assert len(register) == len(set(register)) == 3000
    assert len(queue) == len(set(queue)) == len(batch) == len(set(batch)) == 500
    assert not set(register) & set(queue) and set(queue) == set(batch)
    assert verify["register"]["rows"] == 3000
    assert verify["research_universe"] == {"incomplete_b2b_rows": 3903, "hold_rows_in_universe": 9, "rows": 3894, "processed_rows": 3000, "eligible_after_processed": 894}


def test_wave216_scope_side_effect_and_determinism_guards():
    verify = json.loads((GEN / "rb-b2b-wave216.verification.json").read_text(encoding="utf-8"))
    assert verify["priority"]["overlap_with_processed_register"] == 0
    assert verify["source_planner"]["overlap_with_processed_register"] == 0
    assert verify["source_planner"]["automotive_excluded"] == verify["source_planner"]["electronics_excluded"] == 0
    assert verify["safe_to_apply_records"] == 0
    assert verify["automatic_web_requests"] == verify["automatic_database_queries"] == verify["automatic_database_mutations"] == 0
    assert all(verify["byte_identical_rerun"].values())
