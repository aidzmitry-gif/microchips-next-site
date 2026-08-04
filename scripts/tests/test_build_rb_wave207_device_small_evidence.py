from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave207-device-small-evidence.py"
CSV_PATH = ROOT / "docs/audits/generated/rb-wave207-device-small-evidence.csv"
SUMMARY_PATH = ROOT / "docs/audits/generated/rb-wave207-device-small-evidence.summary.json"
MANIFEST_PATH = ROOT / "docs/imports/rb-verified-oem-identities-wave207-device-small-2026-07-29.json"
INDEX_PATH = ROOT / "docs/audits/sources/wave207-device-small/snapshot-index.json"
LIVE_COLLISIONS_PATH = ROOT / "docs/audits/generated/wave207-device-small-live-identity-collisions.json"
DRY_RUN_PATH = ROOT / "docs/audits/generated/wave207-device-small-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_deterministic() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest())
    assert first == second


def test_exact_bounded_group_counts_and_no_wave206_overlap() -> None:
    data = rows()
    assert len(data) == 58
    assert Counter(row["group"] for row in data) == {
        "Icom": 12,
        "Vertex": 13,
        "Baofeng": 12,
        "Symbol": 1,
        "Yaesu": 1,
        "Casil": 11,
        "Robiton": 7,
        "Minamoto": 1,
    }
    wave206 = set()
    for path in (ROOT / "docs/imports").glob("rb-verified-oem-identities-wave206*.json"):
        wave206.update(row["external_id"] for row in json.loads(path.read_text(encoding="utf-8-sig"))["products"])
    assert not ({row["product_external_id"] for row in data} & wave206)
    assert "bitrix:2708" not in {row["product_external_id"] for row in data}


def test_fail_closed_partition_and_compatibility_policy() -> None:
    data = rows()
    assert Counter(row["partition"] for row in data) == {
        "no_evidence": 52,
        "conflict": 3,
        "exact_safe": 2,
        "compatibility_only": 1,
    }
    compatibility = [row for row in data if row["partition"] == "compatibility_only"]
    assert [row["product_external_id"] for row in compatibility] == ["bitrix:26300"]
    assert all(row["safe_to_apply"] == "false" for row in compatibility)
    assert all(not row["replacement_mpn"] for row in compatibility)
    assert all(row["safe_to_apply"] == "false" for row in data if row["partition"] in {"conflict", "no_evidence"})


def test_snapshots_are_hash_pinned_and_exact_tokens_present() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8-sig"))
    assert len(index["sources"]) == 7
    assert len(index["unavailable"]) == 10
    for source in index["sources"]:
        path = ROOT / source["snapshot_path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["snapshot_sha256"]
        assert all(source["token_counts"][token] > 0 for token in source["required_tokens"])


def test_manifest_contains_only_safe_exact_rows() -> None:
    data = rows()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    products = manifest["products"]
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert [row["external_id"] for row in products] == ["bitrix:2570", "bitrix:2582"]
    assert {row["mpn"] for row in products} == {"BP-210N", "BP-264"}
    assert {row["external_id"] for row in products} == {
        row["product_external_id"] for row in data if row["safe_to_apply"] == "true"
    }
    for row in products:
        snapshot = (MANIFEST_PATH.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]


def test_summary_proves_no_full_name_duplicate() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8-sig"))
    assert summary["strict_full_name_duplicates"] == {}
    assert summary["wave206_overlap_rows"] == 0
    assert summary["safe_to_apply"]["rows"] == 2
    assert summary["policy"]["database_mutations"] == 0


def test_live_database_collision_guard_covers_every_manifest_row() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    guard = json.loads(LIVE_COLLISIONS_PATH.read_text(encoding="utf-8-sig"))
    ids = [row["external_id"] for row in manifest["products"]]
    assert guard["normalizer"] == "App\\Domain\\Imports\\ProductIdentity::normalize"
    assert guard["candidate_rows_checked"] == len(ids)
    assert guard["candidate_external_ids"] == ids
    assert guard["collisions"] == []


def test_laravel_dry_run_matches_the_final_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    dry_run = json.loads(DRY_RUN_PATH.read_text(encoding="utf-8-sig"))
    assert dry_run["exit_code"] == 0
    assert dry_run["mode"] == "dry_run"
    assert dry_run["records"] == len(manifest["products"])
    assert dry_run["manifest_sha256"] == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert dry_run["commercial_fields_changed"] == 0
    assert dry_run["publication_fields_changed"] == 0
