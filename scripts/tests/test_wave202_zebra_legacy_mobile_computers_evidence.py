import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/audits/generated/wave201-industrial-batch-candidates.csv"
OUTPUT = ROOT / "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence-summary.json"
BATCH = "zebra_legacy_mobile_computers"
ALLOWED = {"exact_safe", "compatibility_only", "conflict", "no_evidence"}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave202_partition_is_complete_unique_and_exactly_bounded():
    candidates = [row for row in read_csv(INPUT) if row["batch"] == BATCH]
    evidence = read_csv(OUTPUT)

    assert len(candidates) == 151
    assert len(evidence) == 151
    assert len({row["product_external_id"] for row in evidence}) == 151
    assert {row["product_external_id"] for row in evidence} == {
        row["product_external_id"] for row in candidates
    }
    assert {row["partition"] for row in evidence} <= ALLOWED
    assert all(row["batch"] == BATCH for row in evidence)
    assert all(row["model_tokens"] for row in evidence)


def test_wave202_never_infers_replacement_manufacturer_or_mpn_from_compatibility():
    evidence = read_csv(OUTPUT)
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    exact = [row for row in evidence if row["partition"] == "exact_safe"]

    assert unsafe
    assert all(not row["replacement_manufacturer"] for row in unsafe)
    assert all(not row["replacement_mpn"] for row in unsafe)
    assert all(row["manufacturer_mpn_inference"] == "none" for row in unsafe)
    assert all(row["safe_to_apply"] == "false" for row in unsafe)

    assert {row["product_external_id"] for row in exact} == {
        "bitrix:12162",
        "bitrix:12315",
        "bitrix:12327",
        "bitrix:12409",
        "bitrix:12418",
    }
    assert all(row["replacement_manufacturer"] == "Zebra" for row in exact)
    assert all(row["replacement_mpn"] for row in exact)
    assert all(
        row["manufacturer_mpn_inference"] == "explicit_official_exact_part_only"
        for row in exact
    )

    reused_ids = {
        "bitrix:12162",
        "bitrix:12315",
        "bitrix:12327",
        "bitrix:12409",
        "bitrix:12418",
    }
    reused = [row for row in exact if row["product_external_id"] in reused_ids]
    assert len(reused) == 5
    assert all(row["repeat_handling"] == "previously_processed" for row in reused)
    assert all(row["safe_to_apply"] == "false" for row in reused)

    superseded = [
        row for row in evidence if row["product_external_id"] == "bitrix:12122"
    ]
    assert len(superseded) == 1
    assert superseded[0]["partition"] == "no_evidence"
    assert superseded[0]["repeat_handling"] == "source_superseded"
    assert superseded[0]["safe_to_apply"] == "false"
    assert not superseded[0]["replacement_manufacturer"]
    assert not superseded[0]["replacement_mpn"]
    assert "current official PDF revision 2026-06-23 no longer lists P1083277-002" in superseded[0]["conflict_reason"]
    assert sum(row["safe_to_apply"] == "true" for row in evidence) == 0


def test_wave202_summary_reconciles_and_records_zero_db_mutations():
    evidence = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    counts = {
        partition: sum(row["partition"] == partition for row in evidence)
        for partition in ALLOWED
        if any(row["partition"] == partition for row in evidence)
    }

    assert summary["output"]["rows"] == 151
    assert summary["partition_counts"] == dict(sorted(counts.items()))
    assert summary["policy"]["database_mutations"] == 0
    assert summary["prior_manifest_reuse"]["rows"] == 5
    assert summary["new_exact_source_rows"] == []
    assert summary["source_superseded_rows"] == ["bitrix:12122"]
    assert summary["safe_to_apply"] == {
        "rows": 0,
        "external_ids": [],
    }
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
