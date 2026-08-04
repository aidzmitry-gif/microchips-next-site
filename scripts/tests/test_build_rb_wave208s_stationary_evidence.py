from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave208s-stationary-evidence.py"
CSV_PATH = ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.csv"
SUMMARY_PATH = ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.summary.json"
MANIFEST_PATH = ROOT / "docs/imports/rb-verified-oem-identities-wave208s-stationary-2026-07-29.json"
INDEX_PATH = ROOT / "docs/audits/sources/wave208s-stationary/snapshot-index.json"
LIVE_GUARD_PATH = ROOT / "docs/audits/generated/wave208s-stationary-live-identity-collisions.json"
DRY_RUN_PATH = ROOT / "docs/audits/generated/wave208s-stationary-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_deterministic() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
    assert first == second


def test_bounded_input_and_fail_closed_partition() -> None:
    data = rows()
    assert len(data) == 19
    assert Counter(row["group"] for row in data) == {"Casil": 11, "Robiton": 7, "Minamoto": 1}
    assert Counter(row["partition"] for row in data) == {"exact_safe": 15, "no_evidence": 3, "conflict": 1}
    assert {row["product_external_id"] for row in data if row["partition"] == "no_evidence"} == {
        "bitrix:1191", "bitrix:1409", "bitrix:1543",
    }
    conflict = [row for row in data if row["partition"] == "conflict"]
    assert [row["product_external_id"] for row in conflict] == ["bitrix:1399"]
    assert "bounded-name matcher" in conflict[0]["conflict_reason"]
    assert all(row["safe_to_apply"] == "false" for row in data if row["partition"] != "exact_safe")


def test_only_official_exact_product_snapshots_are_accepted() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
    assert len(index["sources"]) == 16
    assert Counter(source["manufacturer"] for source in index["sources"]) == {"Casil": 10, "ROBITON": 6}
    for source in index["sources"]:
        assert source["source_kind"] == "official_manufacturer_product_page"
        assert urlparse(source["source_url"]).hostname in {"en.casilbattery.com", "www.robiton.ru"}
        snapshot = ROOT / source["snapshot_path"]
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
        assert all(source["token_counts"].get(token, 0) > 0 for token in source["required_tokens"])


def test_manifest_contains_only_exact_safe_rows_and_pinned_snapshots() -> None:
    data = rows()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    products = manifest["products"]
    assert len(products) == 15
    assert {row["external_id"] for row in products} == {
        row["product_external_id"] for row in data if row["safe_to_apply"] == "true"
    }
    assert "bitrix:1399" not in {row["external_id"] for row in products}
    for row in products:
        assert row["source_kind"] == "official_manufacturer_product_page"
        snapshot = (MANIFEST_PATH.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]


def test_duplicate_and_live_collision_guards_are_complete() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8-sig"))
    guard = json.loads(LIVE_GUARD_PATH.read_text(encoding="utf-8-sig"))
    assert summary["duplicate_guard"]["strict_full_name_groups"] == {}
    assert summary["canonical_registry"]["rows"] == 17207
    assert guard["normalizer"] == "App\\Domain\\Imports\\ProductIdentity::normalize"
    assert guard["candidate_rows_checked"] == 16
    assert len(guard["candidate_external_ids"]) == 16
    assert len(guard["candidate_mpn_normalized"]) == 16
    assert guard["query_exit_code"] == 0
    assert guard["collisions"] == []


def test_laravel_dry_run_matches_final_manifest_and_did_not_mutate_db() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    dry_run = json.loads(DRY_RUN_PATH.read_text(encoding="utf-8-sig"))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8-sig"))
    assert dry_run["exit_code"] == 0
    assert dry_run["mode"] == "dry_run"
    assert dry_run["records"] == len(manifest["products"])
    assert dry_run["manifest_sha256"] == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert dry_run["post_run_rows_with_manufacturer_or_mpn"] == 0
    assert dry_run["database_mutations"] == 0
    assert summary["manifest"]["laravel_dry_run_verified"] is True
    assert summary["policy"]["database_mutations"] == 0
