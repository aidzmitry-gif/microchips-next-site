from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave215c-medical-ups-evidence.csv"
SUMMARY = GEN / "rb-wave215c-medical-ups-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215c-medical-ups-2026-07-29.json"
LIVE = GEN / "wave215c-medical-ups-live-identity-collisions.json"
DRY = GEN / "wave215c-medical-ups-laravel-dry-run.json"
SOURCES = ROOT / "docs/audits/sources/wave215c-medical-ups/source-registry.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave215c_exact_medical_plus_enersys_ups_partition() -> None:
    data = rows()
    assert len(data) == len({row["product_external_id"] for row in data}) == 26
    assert Counter(row["lane"] for row in data) == {"medical_b2b": 24, "enersys_ups": 2}
    assert {row["category_external_id"] for row in data if row["lane"] == "medical_b2b"} == {"seo:replacement-medical"}
    assert {row["product_external_id"] for row in data if row["lane"] == "enersys_ups"} == {"bitrix:24517", "bitrix:24518"}
    assert all(row["device_oem"] and row["device_model"] for row in data if row["lane"] == "medical_b2b")
    assert {row["enersys_exact_series"] for row in data if row["lane"] == "enersys_ups"} == {"Cyclon BC Cell", "Cyclon E Cell"}
    assert {row["enersys_catalogue_part_number"] for row in data if row["lane"] == "enersys_ups"} == {"0820-0004", "0850-0004"}


def test_primary_source_registry_and_fail_closed_manifest() -> None:
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    source = sources["sources"][0]
    snapshot = ROOT / source["snapshot_path"]
    assert source["publisher"] == "EnerSys"
    assert snapshot.is_file() and hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["products"]) == 2
    assert {product["mpn"] for product in manifest["products"]} == {"Cyclon BC Cell", "Cyclon E Cell"}
    assert all(row["safe_to_apply"] == "false" for row in rows() if row["lane"] == "medical_b2b")
    assert all(row["safe_to_apply"] == "true" for row in rows() if row["lane"] == "enersys_ups")


def test_partition_registry_live_db_and_laravel_dry_run_guards() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    assert summary["wave215_partition"] == {"a_power_systems": 359, "b_traction": 115, "c_medical_plus_enersys_ups": 26, "disjoint_union_rows": 500, "pairwise_overlap_rows": 0}
    assert summary["processed2500_overlap_ids"] == []
    assert summary["scope_exclusion"] == {"automotive_rows": 0, "electronics_rows": 0}
    assert summary["target"] == {"rows": 26, "medical_b2b_rows": 24, "enersys_ups_rows": 2}
    assert summary["manifest"]["rows"] == summary["safe_to_apply_records"] == 2
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 26 and live["database_mutations"] == 0
    assert dry["exit_code"] == 0 and dry["records"] == 2
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["database_mutations"] == summary["database_mutations"] == 0
