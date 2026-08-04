import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/audits/generated"
OUTPUT = GENERATED / "rb-wave203-commercial-duplicate-guard.csv"
SUMMARY = GENERATED / "rb-wave203-commercial-duplicate-guard-summary.json"
BUILDER = ROOT / "scripts/build-rb-wave203-commercial-duplicate-guard.ps1"


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def wave203_candidates():
    return [
        row
        for row in read_csv(GENERATED / "wave203-industrial-unassigned-preparation.csv")
        if row["recommended_wave"] == "wave203" and row["repeat_handling"] == "new"
    ]


def test_wave203_commercial_guard_covers_the_exact_143_row_union():
    rows = read_csv(OUTPUT)
    candidates = wave203_candidates()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert len(rows) == len(candidates) == 143
    assert len({row["product_external_id"] for row in rows}) == 143
    assert {row["product_external_id"] for row in rows} == {
        row["product_external_id"] for row in candidates
    }
    assert summary["candidate_records"] == 143
    assert summary["evidence_union_records"] == 143
    assert summary["current_db_records"] + summary["current_db_missing_records"] == 143
    assert summary["current_db_missing_records"] == len(summary["current_db_missing_external_ids"])
    assert summary["tinker_batch_size"] <= 25
    assert summary["tinker_batches"] == 8
    assert summary["output_sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()


def test_wave203_commercial_guard_is_read_only_and_blocks_unsupported_claims():
    rows = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert all(row["safe_to_apply"] == "false" for row in rows)
    assert summary["automatic_database_mutations"] == 0
    assert summary["safe_to_apply"] is False
    blocked = [row for row in rows if row["offer_claim_guard"] != "no_unsupported_commercial_claim"]
    assert len(blocked) == summary["unsupported_commercial_claims"]
    assert {row["product_external_id"] for row in blocked} == set(
        summary["unsupported_commercial_external_ids"]
    )
    assert all(
        row["availability"] != "in_stock" or "BLOCK_in_stock_without_stock_evidence" in row["offer_claim_guard"]
        for row in rows
    )
    assert all(
        not row["current_price"]
        or int(row["current_price_evidence_count"]) > 0
        or "BLOCK_price_without_current_evidence" in row["offer_claim_guard"]
        for row in rows
    )


def test_wave203_media_drafts_prices_and_schema_reconcile_to_summary():
    rows = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    sums = {
        "price_evidence_records": "price_evidence_count",
        "current_price_evidence_records": "current_price_evidence_count",
        "media_records": "media_count",
        "published_media_records": "published_media_count",
        "verified_published_media_records": "verified_published_media_count",
        "description_draft_records": "description_draft_count",
        "manufacturer_primary_draft_records": "manufacturer_primary_draft_count",
        "applied_source_draft_records": "applied_source_draft_count",
    }
    for summary_key, row_key in sums.items():
        assert summary[summary_key] == sum(int(row[row_key]) for row in rows)
    assert summary["offer_schema_records"] == sum(
        row["offer_schema_present"] == "true" for row in rows
    )
    assert summary["current_price_records"] == sum(bool(row["current_price"]) for row in rows)


def test_wave203_strict_duplicates_require_part_or_model_voltage_and_capacity():
    rows = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    duplicate_rows = [row for row in rows if row["strict_duplicate_candidate"] == "true"]
    groups = Counter(row["strict_duplicate_group_key"] for row in duplicate_rows)
    assert len(groups) == summary["strict_duplicate_groups"]
    assert len(duplicate_rows) == summary["strict_duplicate_candidates"]
    assert set(groups) == set(summary["strict_duplicate_group_keys"])
    assert all(row["strict_identity_token"] for row in duplicate_rows)
    assert all(row["voltage_v"] for row in duplicate_rows)
    assert all(row["capacity_mah"] for row in duplicate_rows)
    assert all(int(row["strict_duplicate_group_size"]) == groups[row["strict_duplicate_group_key"]] for row in duplicate_rows)
    assert all(size > 1 for size in groups.values())


def test_wave203_builder_uses_bounded_read_only_tinker_batches():
    script = BUILDER.read_text(encoding="utf-8-sig")
    assert "[int]$TinkerBatchSize = 20" in script
    assert "$TinkerBatchSize -gt 25" in script
    assert "for ($attempt = 1; $attempt -le 3; $attempt++)" in script
    assert "->select(" in script
    assert "->selectRaw(" in script
    for forbidden in ("->insert(", "->update(", "->delete(", "->upsert(", "->create(", "->save("):
        assert forbidden not in script
