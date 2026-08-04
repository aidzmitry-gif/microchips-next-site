import csv
import hashlib
import json
import subprocess
import sys
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave203-remaining-evidence.py"
ACQUIRE = ROOT / "scripts/acquire-rb-wave203-remaining-official-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave203-remaining-official-source-evidence.json"
OUTPUT = ROOT / "docs/audits/generated/wave203-remaining-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-remaining-evidence-summary.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave203-remaining/snapshot-index.json"
POS_OUTPUT = ROOT / "docs/audits/generated/wave203-pos-evidence.csv"
CAPTURE_OUTPUT = ROOT / "docs/audits/generated/wave203-capture-evidence.csv"

POS_BRANDS = {"VeriFone", "Ingenico", "Pax", "Castles", "Dejavoo", "FirstData", "Hypercom", "Newpos", "Sagem", "Sunmi", "Bitel"}
CAPTURE_BRANDS = {"CipherLab", "Casio", "Opticon", "Unitech", "LXE", "Bluebird", "Denso", "Handheld", "M3 Mobile", "Psion", "TEKLOGIX"}


def rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_reproducible():
    subprocess.run([sys.executable, str(ACQUIRE)], cwd=ROOT, check=True)
    first_index = SNAPSHOT_INDEX.read_bytes()
    subprocess.run([sys.executable, str(ACQUIRE)], cwd=ROOT, check=True)
    assert SNAPSHOT_INDEX.read_bytes() == first_index
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    first_csv = OUTPUT.read_bytes()
    first_summary = SUMMARY.read_bytes()
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    assert OUTPUT.read_bytes() == first_csv
    assert SUMMARY.read_bytes() == first_summary


def test_three_wave203_partitions_are_disjoint_and_complete():
    recommended = [row for row in rows(INPUT) if row["recommended_wave"] == "wave203" and row["repeat_handling"] == "new"]
    pos = {row["product_external_id"] for row in recommended if row["brand_or_series"] in POS_BRANDS}
    capture = {row["product_external_id"] for row in recommended if row["brand_or_series"] in CAPTURE_BRANDS}
    remaining = {row["product_external_id"] for row in rows(OUTPUT)}
    expected = {row["product_external_id"] for row in recommended}

    assert (len(expected), len(pos), len(capture), len(remaining)) == (143, 42, 74, 27)
    assert not pos & capture
    assert not pos & remaining
    assert not capture & remaining
    assert pos | capture | remaining == expected


def test_actual_three_evidence_outputs_are_disjoint_and_complete():
    recommended = {
        row["product_external_id"]
        for row in rows(INPUT)
        if row["recommended_wave"] == "wave203" and row["repeat_handling"] == "new"
    }
    pos = {row["product_external_id"] for row in rows(POS_OUTPUT)}
    capture = {row["product_external_id"] for row in rows(CAPTURE_OUTPUT)}
    remaining = {row["product_external_id"] for row in rows(OUTPUT)}

    assert (len(pos), len(capture), len(remaining)) == (42, 74, 27)
    assert not pos & capture
    assert not pos & remaining
    assert not capture & remaining
    assert pos | capture | remaining == recommended


def test_fail_closed_identity_policy_and_pinned_exact_sources():
    evidence = rows(OUTPUT)
    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    registry_by_id = {row["product_external_id"]: row for row in registry["evidence"]}

    assert {row["product_external_id"] for row in exact} == {"bitrix:12204", "bitrix:12304", "bitrix:12329"}
    assert all(row["safe_to_apply"] == "true" for row in exact)
    assert all(row["manufacturer_mpn_inference"] == "explicit_official_exact_part_only" for row in exact)
    assert all(row["replacement_manufacturer"] and row["replacement_mpn"] for row in exact)
    assert all(row["snapshot_path"] and row["snapshot_sha256"] for row in exact)
    assert all(hashlib.sha256((ROOT / row["snapshot_path"]).read_bytes()).hexdigest() == row["snapshot_sha256"] for row in exact)
    assert all(registry_by_id[row["product_external_id"]]["identity_assertion"] == "exact_oem_part" for row in exact)
    assert all(registry_by_id[row["product_external_id"]]["source_url"].startswith("https://") for row in exact)

    assert unsafe
    assert all(row["safe_to_apply"] == "false" for row in unsafe)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in unsafe)
    assert all(row["manufacturer_mpn_inference"] == "none" for row in unsafe)
    assert all(not row["snapshot_path"] and not row["snapshot_sha256"] for row in unsafe)


def test_hash_drift_demotes_exact_evidence_to_a_hold():
    spec = importlib.util.spec_from_file_location("wave203_remaining_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    snapshot_index = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    registry["evidence"][0]["snapshot_sha256"] = "0" * 64
    candidate_ids = {row["product_external_id"] for row in rows(OUTPUT)}
    validated = module.validate_registry(registry, candidate_ids, snapshot_index)
    assert validated["bitrix:12204"]["_snapshot_hold_reason"] == "snapshot metadata drifted"


def test_summary_reconciles_and_records_no_database_mutation():
    evidence = rows(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    counts = {name: sum(row["partition"] == name for row in evidence) for name in {row["partition"] for row in evidence}}

    assert summary["output"]["rows"] == 27
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["partition_counts"] == dict(sorted(counts.items()))
    assert summary["cross_partition_coverage"] == {
        "pos_rows": 42,
        "capture_rows": 74,
        "remaining_rows": 27,
        "union_rows": 143,
        "expected_rows": 143,
        "pairwise_overlap_rows": 0,
        "uncovered_rows": 0,
    }
    assert summary["safe_to_apply"] == {
        "rows": 3,
        "external_ids": ["bitrix:12204", "bitrix:12304", "bitrix:12329"],
    }
    assert len(summary["exact_snapshot_evidence"]) == 3
    assert all(record["snapshot_path"] and record["snapshot_sha256"] for record in summary["exact_snapshot_evidence"])
    assert summary["snapshot_validation_holds"] == []
    assert summary["policy"]["database_mutations"] == 0
