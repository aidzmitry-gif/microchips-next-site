import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
def load(name):
    with (GEN / name).open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def test_wave210_no_repeat_and_scope_gates():
    register, queue, batch = load("rb-b2b-processed-register-wave210.csv"), load("rb-b2b-priority-queue-wave210.csv"), load("rb-b2b-next-source-batch-wave210.csv")
    old = load("rb-b2b-processed-register-wave208.csv")
    assert len(register) == len({r["product_external_id"] for r in register}) == 1500
    assert {r["product_external_id"] for r in register} >= {r["product_external_id"] for r in old}
    assert len(queue) == len(batch) == 500
    assert {r["product_external_id"] for r in queue} == {r["product_external_id"] for r in batch}
    assert not ({r["product_external_id"] for r in queue} & {r["product_external_id"] for r in register})
    verify = json.loads((GEN / "rb-b2b-wave210.verification.json").read_text(encoding="utf-8"))
    assert verify["source_planner"]["automotive_excluded"] == verify["source_planner"]["electronics_excluded"] == 0
    assert all(verify["byte_identical_rerun"].values())
    assert verify["automatic_web_requests"] == verify["automatic_database_mutations"] == 0
