import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACQUIRE = ROOT / "scripts/acquire-rb-wave204-radio-official-evidence.py"
BUILDER = ROOT / "scripts/build-rb-wave204-radio-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-radio-official-source-evidence.json"
INDEX = ROOT / "docs/audits/sources/wave204-radio/snapshot-index.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-radio-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-radio-evidence-summary.json"


def rows(path):
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


def test_all_41_new_radio_rows_are_covered_without_prior_repeats():
    candidates = {
        row["product_external_id"]
        for row in rows(INPUT)
        if row["family"] == "radio_station_battery_packs" and row["repeat_handling"] == "new"
    }
    evidence = rows(OUTPUT)
    assert len(candidates) == len(evidence) == 41
    assert {row["product_external_id"] for row in evidence} == candidates
    assert all(row["repeat_handling"] != "previously_processed" for row in evidence)


def test_exact_rows_require_primary_pinned_exact_evidence():
    evidence = rows(OUTPUT)
    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    assert {row["product_external_id"] for row in exact} == {
        "bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397",
    }
    assert all(row["source_tier"] == "manufacturer_primary" for row in exact)
    assert all(row["source_url"].startswith("https://www.alinco.com/") for row in exact)
    assert all(row["replacement_manufacturer"] == "Alinco" and row["replacement_mpn"] for row in exact)
    assert all(row["snapshot_path"] and row["snapshot_sha256"] for row in exact)
    assert all(hashlib.sha256((ROOT / row["snapshot_path"]).read_bytes()).hexdigest() == row["snapshot_sha256"] for row in exact)
    assert all(row["safe_to_apply"] == "true" for row in exact)
    assert all(row["safe_to_apply"] == "false" for row in unsafe)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in unsafe)
    assert all(not row["snapshot_path"] and not row["snapshot_sha256"] for row in unsafe)


def test_aftermarket_compatibility_and_duplicate_lookalike_fail_closed():
    by_id = {row["product_external_id"]: row for row in rows(OUTPUT)}
    aftermarket = by_id["bitrix:2391"]
    oem = by_id["bitrix:2395"]
    assert aftermarket["partition"] == "compatibility_only"
    assert aftermarket["safe_to_apply"] == "false"
    assert "offered Ajetrays replacement pack" in aftermarket["conflict_reason"]
    assert aftermarket["duplicate_review"] == oem["duplicate_review"] == "lookalike_variant_not_strict_duplicate"
    assert not aftermarket["strict_duplicate_cluster"] and not oem["strict_duplicate_cluster"]
    assert all(not row["strict_duplicate_cluster"] for row in by_id.values())


def test_hash_or_token_drift_demotes_exact_evidence():
    spec = importlib.util.spec_from_file_location("wave204_radio_builder", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    index = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    candidate_ids = {row["product_external_id"] for row in rows(OUTPUT)}
    index["sources"][0]["token_counts"]["EBP-50N"] = 0
    validated = module.validate_registry(registry, candidate_ids, index)
    assert validated["bitrix:2394"]["_snapshot_hold_reason"] == "snapshot lacks one or more row-exact tokens"


def test_summary_reconciles_and_records_zero_mutations():
    evidence = rows(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    counts = {name: sum(row["partition"] == name for row in evidence) for name in {row["partition"] for row in evidence}}
    assert summary["output"]["rows"] == 41
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["partition_counts"] == dict(sorted(counts.items())) == {
        "compatibility_only": 1, "exact_safe": 4, "no_evidence": 36,
    }
    assert summary["safe_to_apply"] == {
        "rows": 4,
        "external_ids": ["bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397"],
    }
    assert summary["prior_evidence_overlap_rows"] == 0
    assert summary["strict_duplicates"] == {"clusters": 0, "rows": 0}
    assert summary["policy"]["database_mutations"] == 0
