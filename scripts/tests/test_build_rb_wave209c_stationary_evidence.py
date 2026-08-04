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
SCRIPT = ROOT / "scripts/build-rb-wave209c-stationary-evidence.py"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave209c-stationary-2026-07-29.json"
SOURCES = ROOT / "docs/audits/sources/wave209c-stationary/source-registry.json"
LIVE = ROOT / "docs/audits/generated/wave209c-stationary-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave209c-stationary-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave209c_is_deterministic_and_bounded() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    before = (hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    after = (hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert before == after
    assert len(rows()) == 81
    assert Counter(row["manufacturer_cluster"] for row in rows()) == {
        "B.B. Battery": 11, "CSB": 9, "Casil": 3, "Panasonic": 3, "Robiton": 2,
        "Sprinter": 6, "Ventura": 25, "WBR": 10, "Yuasa": 12,
    }


def test_primary_snapshots_and_exact_manifest_only() -> None:
    index = json.loads(SOURCES.read_text(encoding="utf-8"))
    for source in index["sources"]:
        assert urlparse(source["source_url"]).scheme == "https"
        snapshot = ROOT / source["snapshot_path"]
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
    data = rows()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {item["external_id"] for item in manifest["products"]} == {row["product_external_id"] for row in data if row["safe_to_apply"] == "true"}
    assert all(row["partition"] == "exact_safe" for row in data if row["safe_to_apply"] == "true")
    assert all(item["source_kind"].startswith("official_manufacturer_") for item in manifest["products"])


def test_no_repeat_scope_and_collision_guards() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    assert summary["previous_wave_exclusion"]["overlap_ids"] == []
    assert summary["scope_exclusion"] == {"automotive_rows": 0, "electronics_rows": 0}
    assert live["query_exit_code"] == 0
    assert live["candidate_rows_checked"] == 26
    assert live["candidate_rows_with_manufacturer_or_mpn"] == []
    assert summary["policy"]["database_mutations"] == 0


def test_laravel_dry_run_matches_manifest_and_did_not_mutate_database() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    dry_run = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    assert dry_run["mode"] == "dry_run"
    assert dry_run["exit_code"] == 0
    assert dry_run["records"] == len(json.loads(MANIFEST.read_text(encoding="utf-8"))["products"])
    assert dry_run["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry_run["commercial_fields_changed"] == 0
    assert dry_run["publication_fields_changed"] == 0
    assert dry_run["post_run_rows_with_manufacturer_or_mpn"] == 0
    assert dry_run["database_mutations"] == 0
    assert summary["manifest"]["laravel_dry_run_verified"] is True
