import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "docs/audits/generated"
BUILDER = ROOT / "scripts/build-rb-wave204-commercial-duplicate-guard.py"
OUTPUT = GENERATED / "rb-wave204-commercial-duplicate-guard.csv"
SUMMARY = GENERATED / "rb-wave204-commercial-duplicate-guard-summary.json"
EVIDENCE_FILES = {
    "wave204-radio-evidence.csv": 41,
    "wave204-industrial-cell-evidence.csv": 34,
    "wave204-remote-control-evidence.csv": 31,
}


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evidence_union():
    rows = []
    for name, expected in EVIDENCE_FILES.items():
        evidence = read_csv(GENERATED / name)
        assert len(evidence) == expected
        rows.extend(evidence)
    return rows


def test_wave204_guard_covers_exact_disjoint_41_34_31_union():
    evidence = evidence_union()
    guarded = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert len(evidence) == len(guarded) == 106
    assert len({row["product_external_id"] for row in evidence}) == 106
    assert len({row["product_external_id"] for row in guarded}) == 106
    assert {row["product_external_id"] for row in evidence} == {
        row["product_external_id"] for row in guarded
    }
    assert summary["candidate_records"] == summary["evidence_union_records"] == 106
    assert summary["evidence_file_rows"] == EVIDENCE_FILES
    assert summary["current_db_records"] + summary["current_db_missing_records"] == 106
    assert summary["current_db_missing_records"] == len(summary["current_db_missing_external_ids"])
    assert summary["output_sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()


def test_wave204_guard_is_read_only_and_blocks_every_unsupported_claim():
    guarded = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert all(row["safe_to_apply"] == "false" for row in guarded)
    assert summary["safe_to_apply"] is False
    assert summary["automatic_database_mutations"] == 0
    blocked = [row for row in guarded if row["offer_claim_guard"] != "no_unsupported_commercial_claim"]
    assert len(blocked) == summary["unsupported_commercial_claims"]
    assert {row["product_external_id"] for row in blocked} == set(summary["unsupported_commercial_external_ids"])
    assert all(
        row["availability"] != "in_stock"
        or "BLOCK_in_stock_without_stock_evidence" in row["offer_claim_guard"]
        for row in guarded
    )
    assert all(
        not row["current_price"]
        or int(row["current_price_evidence_count"]) > 0
        or "BLOCK_price_without_current_evidence" in row["offer_claim_guard"]
        for row in guarded
    )
    assert all(
        row["offer_schema_present"] != "true"
        or (
            row["current_price"]
            and int(row["current_price_evidence_count"]) > 0
            and row["availability"] != "in_stock"
        )
        or "BLOCK_" in row["offer_claim_guard"]
        for row in guarded
    )


def test_wave204_current_snapshot_keeps_legacy_commercial_claims_unpublished():
    guarded = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert summary["current_db_records"] == summary["rb_site_product_records"] == 106
    assert summary["current_price_records"] == 0
    assert summary["currency_records"] == 0
    assert summary["in_stock_records"] == 0
    assert summary["offer_schema_records"] == 0
    assert summary["legacy_price_claim_records"] == 104
    assert summary["legacy_in_stock_claim_records"] == 106
    assert all(row["current_product"] == "true" and row["rb_site_product_count"] == "1" for row in guarded)
    assert all(row["current_name"] == row["legacy_name"] for row in guarded)
    assert all(row["availability"] == "on_request" for row in guarded)


def test_wave204_media_drafts_prices_and_schema_reconcile():
    guarded = read_csv(OUTPUT)
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
    for summary_key, field in sums.items():
        assert summary[summary_key] == sum(int(row[field]) for row in guarded)
    assert summary["offer_schema_records"] == sum(row["offer_schema_present"] == "true" for row in guarded)
    assert summary["current_price_records"] == sum(bool(row["current_price"]) for row in guarded)


def test_wave204_strict_duplicates_require_identity_voltage_and_capacity():
    guarded = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    duplicates = [row for row in guarded if row["strict_duplicate_candidate"] == "true"]
    groups = Counter(row["strict_duplicate_group_key"] for row in duplicates)
    assert len(groups) == summary["strict_duplicate_groups"]
    assert len(duplicates) == summary["strict_duplicate_candidates"]
    assert set(groups) == set(summary["strict_duplicate_group_keys"])
    assert all(row["strict_identity_token"] and row["voltage_v"] and row["capacity_mah"] for row in duplicates)
    assert all(int(row["strict_duplicate_group_size"]) == groups[row["strict_duplicate_group_key"]] for row in duplicates)
    assert all(size > 1 for size in groups.values())


def test_wave204_builder_uses_bounded_read_only_tinker_batches():
    script = BUILDER.read_text(encoding="utf-8-sig")
    assert "DEFAULT_BATCH_SIZE = 20" in script
    assert "1 <= batch_size <= 25" in script
    assert "for _attempt in range(3)" in script
    assert '"->select(' in script
    assert '"->selectRaw(' in script
    assert '["docker", "compose", "exec", "-T", "backend"' in script
    for forbidden in ("->insert(", "->update(", "->delete(", "->upsert(", "->create(", "->save("):
        assert forbidden not in script


def test_wave204_summary_pins_all_inputs_and_bounded_batches():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert summary["tinker_batch_size"] == 20
    assert summary["tinker_batches"] == 6
    for name in EVIDENCE_FILES:
        assert summary["evidence_input_sha256"][name] == hashlib.sha256((GENERATED / name).read_bytes()).hexdigest()
    assert len(summary["property_values_sha256"]) == 64
