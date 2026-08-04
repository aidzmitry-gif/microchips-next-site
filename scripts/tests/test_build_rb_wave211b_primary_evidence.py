import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/audits/generated/rb-wave211b-delta-fiamm-leoch-csb-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave211b-delta-fiamm-leoch-csb-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave211b-delta-2026-07-29.json"
LIVE = ROOT / "docs/audits/generated/wave211b-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave211b-laravel-dry-run.json"


def rows():
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave211b_pinned_union_no_repeat_and_scope_gates():
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert data["input"]["rows"] == 158
    assert data["input"]["manufacturer_counts"] == {"CSB": 22, "Delta": 66, "Fiamm": 43, "Leoch": 27}
    assert data["previous_evidence_exclusion"]["rows"] == 18
    assert data["scope_exclusion"]["automotive_or_starter_rows"] == 0
    assert data["scope_exclusion"]["electronics_component_rows"] == 0
    assert data["medical_oem_device_holds"] == {"rows": 2, "external_ids": ["bitrix:11255", "bitrix:11257"]}
    assert data["eligible"]["rows"] == 140
    assert Counter(row["manufacturer_cluster"] for row in rows()) == {"Delta": 48, "Fiamm": 43, "Leoch": 27, "CSB": 22}
    medical = {row["product_external_id"]: row for row in rows()}
    for external_id in ("bitrix:11255", "bitrix:11257"):
        assert medical[external_id]["partition"] == "no_evidence"
        assert medical[external_id]["safe_to_apply"] == "false"
        assert "Medical specialist/OEM device" in medical[external_id]["conflict_reason"]


def test_exact_is_primary_pinned_and_manifest_is_exact_safe_subset():
    data = rows()
    exact = [row for row in data if row["partition"] == "exact"]
    assert len(exact) == 1
    for row in exact:
        snapshot = ROOT / row["snapshot_path"]
        assert row["source_tier"] == "manufacturer_primary"
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["snapshot_sha256"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {item["external_id"] for item in manifest["products"]} == {row["product_external_id"] for row in data if row["safe_to_apply"] == "true"}
    assert all(item["source_kind"] == "official_manufacturer_product_page" for item in manifest["products"])
    assert all(row["safe_to_apply"] == "false" for row in data if row["manufacturer_cluster"] in {"Fiamm", "Leoch", "CSB"})


def test_full_registry_live_guard_and_dry_run_are_zero_mutation():
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    assert live["query_exit_code"] == 0
    assert live["candidate_rows_checked"] == 18
    assert len(live["collisions"]) == 17
    assert data["live_collision_guard"]["collision_rows"] == 17
    assert data["partition_counts"] == {"conflict": 17, "exact": 1, "no_evidence": 122}
    assert dry["mode"] == "dry_run" and dry["exit_code"] == 0 and dry["apply_flag_used"] is False
    assert dry["records"] == 1 and dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["commercial_fields_changed"] == 0 and dry["publication_fields_changed"] == 0 and dry["database_mutations"] == 0
    assert data["policy"]["database_mutations"] == 0
