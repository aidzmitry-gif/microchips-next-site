import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACQUIRE = ROOT / "scripts/acquire-rb-wave204-remote-control-evidence.py"
BUILDER = ROOT / "scripts/build-rb-wave204-remote-control-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-remote-control-official-source-evidence.json"
INDEX = ROOT / "docs/audits/sources/wave204-remote-control/snapshot-index.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-remote-control-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-remote-control-evidence-summary.json"

EXACT_IDS = {
    "bitrix:20045", "bitrix:20049", "bitrix:20050",
    "bitrix:20059", "bitrix:20060", "bitrix:20061",
    "bitrix:20071", "bitrix:20073", "bitrix:20075",
}
CONFLICT_IDS = {"bitrix:20072", "bitrix:20074"}


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_acquisition_and_builder_are_reproducible():
    subprocess.run([sys.executable, str(ACQUIRE)], cwd=ROOT, check=True)
    first_index = INDEX.read_bytes()
    subprocess.run([sys.executable, str(ACQUIRE)], cwd=ROOT, check=True)
    assert INDEX.read_bytes() == first_index

    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    first_csv = OUTPUT.read_bytes()
    first_summary = SUMMARY.read_bytes()
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    assert OUTPUT.read_bytes() == first_csv
    assert SUMMARY.read_bytes() == first_summary


def test_all_31_remote_control_rows_are_partitioned_once():
    candidates = [row for row in rows(INPUT) if row["family"] == "industrial_remote_control_batteries"]
    evidence = rows(OUTPUT)
    assert len(candidates) == len(evidence) == 31
    assert len({row["product_external_id"] for row in evidence}) == 31
    assert {row["product_external_id"] for row in evidence} == {
        row["product_external_id"] for row in candidates
    }
    assert {row["partition"] for row in evidence} == {"exact_safe", "conflict", "no_evidence"}


def test_exact_rows_have_pinned_primary_evidence_and_no_claim_leakage():
    evidence = rows(OUTPUT)
    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    assert {row["product_external_id"] for row in exact} == EXACT_IDS
    assert all(row["safe_to_apply"] == "true" for row in exact)
    assert all(row["replacement_manufacturer"] and row["replacement_mpn"] for row in exact)
    assert all(row["manufacturer_mpn_inference"] == "explicit_official_exact_part_only" for row in exact)
    assert all(row["source_url"].startswith("https://") for row in exact)
    assert all(row["snapshot_path"] and len(row["snapshot_sha256"]) == 64 for row in exact)
    assert all(
        hashlib.sha256((ROOT / row["snapshot_path"]).read_bytes()).hexdigest()
        == row["snapshot_sha256"]
        for row in exact
    )
    assert all(row["safe_to_apply"] == "false" for row in unsafe)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in unsafe)
    assert all(row["manufacturer_mpn_inference"] == "none" for row in unsafe)


def test_conflicts_are_explicit_and_do_not_apply_identity():
    conflicts = [row for row in rows(OUTPUT) if row["partition"] == "conflict"]
    assert {row["product_external_id"] for row in conflicts} == CONFLICT_IDS
    assert all(row["source_tier"] in {"manufacturer_primary", "manufacturer_service_primary"} for row in conflicts)
    assert all(row["snapshot_path"] and row["snapshot_sha256"] for row in conflicts)
    assert all(row["conflict_reason"] for row in conflicts)
    assert "NiCd" in next(row for row in conflicts if row["product_external_id"] == "bitrix:20072")["verified_facts"]
    assert "Li-ion" in next(row for row in conflicts if row["product_external_id"] == "bitrix:20074")["verified_facts"]


def test_strict_duplicate_scan_is_fail_closed_and_summary_reconciles():
    evidence = rows(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert all(row["strict_duplicate_candidate"] == "false" for row in evidence)
    assert all(row["strict_duplicate_group_size"] == "0" for row in evidence)
    assert summary["partition_counts"] == {"conflict": 2, "exact_safe": 9, "no_evidence": 20}
    assert summary["safe_to_apply"] == {"rows": 9, "external_ids": sorted(EXACT_IDS)}
    assert summary["strict_duplicate_candidates"] == {"rows": 0, "external_ids": []}
    assert summary["output"]["rows"] == 31
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["policy"]["database_mutations"] == 0


def test_snapshot_hash_drift_is_rejected():
    spec = importlib.util.spec_from_file_location("wave204_remote_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    candidates = {
        row["product_external_id"]: row
        for row in rows(INPUT)
        if row["family"] == "industrial_remote_control_batteries"
    }
    original = module.sha256
    module.sha256 = lambda path: "0" * 64 if "autec-mbm06mh" in path.name else original(path)
    try:
        try:
            module.validate_registry(candidates)
        except SystemExit as error:
            assert "Snapshot hash mismatch: bitrix:20045" in str(error)
        else:
            raise AssertionError("snapshot hash drift was accepted")
    finally:
        module.sha256 = original


def test_registry_has_only_primary_official_sources():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    index = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    source_ids = {source["source_id"] for source in index["sources"]}
    assert len(registry["evidence"]) == 11
    assert all(row["source_id"] in source_ids for row in registry["evidence"])
    assert all(row["source_tier"] in {"manufacturer_primary", "manufacturer_service_primary"} for row in registry["evidence"])
    assert all(row["source_url"].startswith("https://") for row in registry["evidence"])
