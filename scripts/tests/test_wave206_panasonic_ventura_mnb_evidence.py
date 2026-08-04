import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave206-panasonic-ventura-mnb-evidence.py"
OUTPUT = ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence-summary.json"
INDEX = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave206-panasonic-ventura-mnb-2026-07-29.json"


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_reproducible_and_covers_exact_scope():
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    first = (OUTPUT.read_bytes(), SUMMARY.read_bytes(), MANIFEST.read_bytes())
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True)
    assert (OUTPUT.read_bytes(), SUMMARY.read_bytes(), MANIFEST.read_bytes()) == first
    evidence = rows(OUTPUT)
    assert len(evidence) == len({row["product_external_id"] for row in evidence}) == 85
    assert Counter(row["manufacturer"] for row in evidence) == Counter({"Panasonic": 34, "Ventura": 28, "MNB": 23})


def test_partition_is_exhaustive_and_fail_closed():
    evidence = rows(OUTPUT)
    assert Counter(row["partition"] for row in evidence) == Counter({
        "exact_safe": 29,
        "compatibility": 5,
        "conflict": 5,
        "no_evidence": 46,
    })
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    assert all(row["safe_to_apply"] == "false" for row in unsafe)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in unsafe)
    assert all(row["conflict_reason"] for row in evidence if row["partition"] == "conflict")
    assert all(row["unsupported_legacy_claims"] for row in evidence if row["partition"] in {"compatibility", "no_evidence"})


def test_exact_rows_have_hash_pinned_model_tokens_and_specs():
    evidence = rows(OUTPUT)
    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    assert len(exact) == 29
    for row in exact:
        snapshot = ROOT / row["snapshot_path"]
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["snapshot_sha256"]
        assert row["required_exact_tokens"] == row["replacement_mpn"] == row["model"]
        assert all(count > 0 for count in json.loads(row["required_token_counts"]).values())
        assert row["verified_voltage_v"] and row["verified_capacity_ah"] and row["verified_technology"]


def test_ventura_conflicts_and_watt_rated_compatibility_are_not_promoted():
    by_id = {row["product_external_id"]: row for row in rows(OUTPUT)}
    assert by_id["bitrix:1471"]["partition"] == "conflict"
    assert "130 Ah" in by_id["bitrix:1471"]["conflict_reason"]
    assert by_id["bitrix:1467"]["partition"] == "conflict"
    assert by_id["bitrix:1466"]["partition"] == "exact_safe"
    assert by_id["bitrix:1466"]["safe_to_apply"] == "false"
    assert by_id["bitrix:1466"]["duplicate_cluster_ids"] == "bitrix:1467"
    for external_id in {"bitrix:1441", "bitrix:1443", "bitrix:1517", "bitrix:1525", "bitrix:1568"}:
        assert by_id[external_id]["partition"] == "compatibility"
        assert not by_id[external_id]["verified_capacity_ah"]


def test_decimal_model_identity_does_not_create_false_duplicate():
    by_id = {row["product_external_id"]: row for row in rows(OUTPUT)}
    assert by_id["bitrix:1408"]["model"] == "MS 1.2-6 F1"
    assert by_id["bitrix:1490"]["model"] == "MS 12-6 F1"
    assert not by_id["bitrix:1408"]["duplicate_cluster_ids"]
    assert not by_id["bitrix:1490"]["duplicate_cluster_ids"]


def test_summary_and_source_index_reconcile():
    evidence = rows(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    index = json.loads(INDEX.read_text(encoding="utf-8-sig"))
    assert summary["partition_counts"] == dict(sorted(Counter(row["partition"] for row in evidence).items()))
    assert summary["output"]["rows"] == 85
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["safe_to_apply"]["rows"] == 25
    assert summary["duplicate_guard"]["rows_with_strict_title_or_manufacturer_model_peers"] == 5
    assert summary["live_collision_guard"]["candidate_rows_checked"] == 28
    assert summary["live_collision_guard"]["collision_rows"] == 3
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    safe_ids = {row["product_external_id"] for row in evidence if row["safe_to_apply"] == "true"}
    assert len(manifest["products"]) == summary["laravel_manifest"]["rows"] == 25
    assert {row["external_id"] for row in manifest["products"]} == safe_ids
    assert summary["policy"] == {
        "primary_manufacturer_sources_only": True,
        "price_stock_media_publication_authorized": False,
        "database_mutations": 0,
    }
    assert len(index["sources"]) == 3
    for source in index["sources"]:
        path = ROOT / source["snapshot_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["snapshot_sha256"]
