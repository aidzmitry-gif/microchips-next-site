from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
REGISTER = GEN / "rb-b2b-processed-register-wave220.csv"
QUEUE = GEN / "rb-b2b-priority-queue-wave220.csv"
VERIFY = GEN / "rb-b2b-wave220-closure.verification.json"
RECONCILIATION = GEN / "rb-b2b-wave220-live-collapse-reconciliation.csv"


def ids(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row["product_external_id"] for row in csv.DictReader(handle)]


def test_wave220_exactly_closes_the_fixed_research_universe() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    processed = ids(REGISTER)
    assert len(processed) == len(set(processed)) == 3894
    assert verify["lineage"] == {"processed3500": 3500, "wave219a": 277, "wave219b": 60, "wave219c": 57, "wave219_total": 394, "pairwise_overlap_ids": []}
    assert verify["historical_research_universe"] == {"source": "docs/audits/generated/rb-full-content-readiness-wave172-after.csv", "incomplete_b2b_rows": 3903, "hold_rows_in_universe": 9, "rows": 3894}
    assert verify["historical_closure"] == {"processed_rows": 3894, "unique_processed_ids": 3894, "missing_ids": [], "extra_ids": [], "duplicate_ids": [], "equals_fixed_research_universe": True}


def test_wave220_has_no_remaining_queue_or_scope_leakage() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert ids(QUEUE) == []
    assert verify["historical_remaining_queue"]["rows"] == verify["historical_remaining_queue"]["eligible_unreviewed_unprocessed"] == verify["historical_remaining_queue"]["selected_records"] == 0
    assert verify["scope"] == {"automotive_leak_ids": [], "electronics_leak_ids": [], "non_b2b_leak_ids": []}
    assert all(verify["byte_identical_rerun"].values())
    assert verify["automatic_web_requests"] == verify["automatic_database_queries"] == verify["automatic_database_mutations"] == 0
    assert verify["apply_performed"] is False


def test_wave220_reconciles_only_the_six_authorized_live_absences() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    reconciliation = list(csv.DictReader(RECONCILIATION.open(encoding="utf-8-sig", newline="")))
    live = verify["live_wave221_reconciliation"]
    assert live["source"] == "docs/audits/generated/rb-full-content-readiness-wave221-after.csv"
    assert live["live_b2b_rows"] == 4337
    assert live["historical_ledger_ids_present"] == 3888
    assert live["historical_ledger_ids_absent"] == ["bitrix:12270", "bitrix:24006", "bitrix:24007", "bitrix:24008", "bitrix:24009", "bitrix:24052"]
    assert live["live_b2b_ids_outside_historical_ledger"] == 449
    assert live["historical_ledger_is_live_universe"] is False
    assert [(row["historical_external_id"], row["survivor_external_id"], row["collapse_kind"]) for row in reconciliation] == [
        ("bitrix:12270", "bitrix:12116", "wave174_honeywell_family"),
        ("bitrix:24006", "bitrix:12130", "wave202_strict_duplicate"),
        ("bitrix:24007", "bitrix:12146", "wave202_strict_duplicate"),
        ("bitrix:24008", "bitrix:12139", "wave202_strict_duplicate"),
        ("bitrix:24009", "bitrix:12142", "wave202_strict_duplicate"),
        ("bitrix:24052", "bitrix:12149", "wave201_strict_duplicate"),
    ]
