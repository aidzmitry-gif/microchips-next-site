import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/audits/generated"


def _read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_wave202_commercial_guard_is_complete_and_source_aligned():
    rows = _read_csv(GENERATED / "rb-wave202-commercial-duplicate-guard.csv")
    candidates = [
        row
        for row in _read_csv(GENERATED / "wave201-industrial-batch-candidates.csv")
        if row["batch"]
        in {
            "zebra_legacy_mobile_computers",
            "honeywell_mobile_computers",
            "datalogic_data_capture",
            "intermec_mobile_computers",
        }
    ]
    summary = json.loads(
        (GENERATED / "rb-wave202-commercial-duplicate-guard-summary.json").read_text(
            encoding="utf-8-sig"
        )
    )

    assert len(rows) == 237
    assert len({row["product_external_id"] for row in rows}) == 237
    assert {row["product_external_id"] for row in rows} == {
        row["product_external_id"] for row in candidates
    }
    assert Counter(row["batch"] for row in rows) == Counter(
        row["batch"] for row in candidates
    )
    assert summary["candidate_records"] == 237
    assert summary["current_db_records"] + summary["current_db_missing_records"] == 237
    assert summary["rb_site_product_records"] <= summary["current_db_records"]
    assert summary["batch_counts"] == dict(Counter(row["batch"] for row in rows))


def test_wave202_commercial_guard_is_read_only_and_claim_safe():
    rows = _read_csv(GENERATED / "rb-wave202-commercial-duplicate-guard.csv")
    summary = json.loads(
        (GENERATED / "rb-wave202-commercial-duplicate-guard-summary.json").read_text(
            encoding="utf-8-sig"
        )
    )

    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert all(
        row["offer_claim_guard"] == "no_unsupported_commercial_claim" for row in rows
    )
    assert summary["unsupported_commercial_claims"] == 0
    assert summary["in_stock_records"] == 0
    assert summary["automatic_database_mutations"] == 0
    assert summary["safe_to_apply"] is False


def test_wave202_duplicate_and_no_repeat_counts_are_explicit():
    rows = _read_csv(GENERATED / "rb-wave202-commercial-duplicate-guard.csv")
    summary = json.loads(
        (GENERATED / "rb-wave202-commercial-duplicate-guard-summary.json").read_text(
            encoding="utf-8-sig"
        )
    )

    duplicate_rows = [row for row in rows if row["strict_duplicate_candidate"] == "true"]
    duplicate_groups = {row["strict_duplicate_group_key"] for row in duplicate_rows}
    assert len(duplicate_rows) == summary["strict_duplicate_candidates"] == 8
    assert len(duplicate_groups) == summary["strict_duplicate_groups"] == 4
    assert all(int(row["strict_duplicate_group_size"]) == 2 for row in duplicate_rows)
    assert sum(row["previously_processed"] == "true" for row in rows) == 9
    assert summary["previously_processed_records"] == 9
