import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave204-industrial-cell-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave204-industrial-cell-official-source-evidence.json"
OUTPUT = ROOT / "docs/audits/generated/wave204-industrial-cell-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave204-industrial-cell-evidence-summary.json"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave204-industrial-cells/snapshot-index.json"


def rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_reproducible_and_covers_the_exact_family():
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    first = (OUTPUT.read_bytes(), SUMMARY.read_bytes(), SNAPSHOT_INDEX.read_bytes())
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    assert (OUTPUT.read_bytes(), SUMMARY.read_bytes(), SNAPSHOT_INDEX.read_bytes()) == first

    expected = {
        row["product_external_id"] for row in rows(INPUT)
        if row["family"] == "legacy_industrial_traction_cells"
    }
    actual = {row["product_external_id"] for row in rows(OUTPUT)}
    assert len(expected) == len(actual) == 34
    assert actual == expected


def test_exact_safe_requires_primary_snapshot_hash_and_all_exact_tokens():
    evidence = rows(OUTPUT)
    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    assert [row["product_external_id"] for row in exact] == ["bitrix:2239"]
    row = exact[0]
    assert row["safe_to_apply"] == "true"
    assert row["replacement_manufacturer"] == "Danfoss"
    assert row["replacement_mpn"] == "BT06K ATEX"
    assert row["verified_chemistry"] == "NiMH"
    assert row["verified_capacity_mah"] == "600"
    assert row["verified_voltage_v"] == "4.8"
    assert row["source_url"].startswith("https://assets.danfoss.com/")
    assert row["related_variant_ids"] == "bitrix:20078"
    assert row["duplicate_decision"] == "unique_exact_mpn_distinct_variant_reviewed"
    snapshot = ROOT / row["snapshot_path"]
    assert snapshot.is_file()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["snapshot_sha256"]
    token_counts = json.loads(row["required_token_counts"])
    assert set(token_counts) == {"BT06K ATEX", "NiMH", "600mAh", "4,8 Vdc"}
    assert all(count > 0 for count in token_counts.values())


def test_conflicts_and_no_evidence_never_infer_identity_or_specs():
    evidence = rows(OUTPUT)
    conflicts = [row for row in evidence if row["partition"] == "conflict"]
    no_evidence = [row for row in evidence if row["partition"] == "no_evidence"]
    assert len(conflicts) == 8
    assert len(no_evidence) == 25
    unsafe = conflicts + no_evidence
    assert all(row["safe_to_apply"] == "false" for row in unsafe)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in unsafe)
    assert all(not row["verified_model"] and not row["verified_chemistry"] for row in unsafe)
    assert all(not row["verified_capacity_mah"] and not row["verified_voltage_v"] for row in unsafe)
    assert all(row["conflict_reason"] for row in unsafe)


def test_duplicate_gate_and_summary_reconcile():
    evidence = rows(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    counts = Counter(row["partition"] for row in evidence)
    assert summary["partition_counts"] == dict(sorted(counts.items()))
    assert summary["output"]["rows"] == 34
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["duplicates"]["normalized_exact_title_rows"] == 0
    assert summary["duplicates"]["rows"] == []
    assert summary["duplicates"]["exact_manufacturer_mpn_collisions"] == 0
    assert summary["duplicates"]["distinct_variant_reviews"] == [{
        "product_external_id": "bitrix:2239",
        "related_variant_ids": ["bitrix:20078"],
        "decision": "unique_exact_mpn_distinct_variant_reviewed",
    }]
    assert summary["safe_to_apply"] == {"rows": 1, "external_ids": ["bitrix:2239"]}
    assert summary["policy"]["database_mutations"] == 0


def test_registry_and_snapshot_index_are_fully_pinned_primary_sources():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    snapshot_index = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    assert registry["policy"]["primary_manufacturer_sources_only"] is True
    assert len(snapshot_index["sources"]) == 6
    for source in snapshot_index["sources"]:
        assert source["source_tier"] in {"manufacturer_datasheet_primary", "manufacturer_catalogue_primary"}
        path = ROOT / source["snapshot_path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["snapshot_sha256"] == source["verified_sha256"]
    assert snapshot_index["exact_token_evidence"][0]["product_external_id"] == "bitrix:2239"
