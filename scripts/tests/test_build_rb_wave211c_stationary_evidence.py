from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave211c-stationary-2026-07-29.json"
SOURCES = ROOT / "docs/audits/sources/wave211c-stationary/source-registry.json"
LIVE = ROOT / "docs/audits/generated/wave211c-stationary-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave211c-stationary-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave211c_target_union_and_fail_closed_partitions() -> None:
    data = rows()
    assert len(data) == 129
    assert Counter(row["manufacturer_cluster"] for row in data) == {
        "Sonnenschein": 40, "Yuasa": 23, "Panasonic": 15, "MNB": 24,
        "Sprinter": 10, "WBR": 16, "EnerSys": 1,
    }
    assert Counter(row["partition"] for row in data) == {"exact_safe": 50, "conflict": 1, "no_evidence": 78}
    assert {row["product_external_id"] for row in data if row["partition"] == "conflict"} == {"bitrix:2938"}
    assert all(row["safe_to_apply"] == "false" for row in data if row["partition"] != "exact_safe")


def test_primary_snapshots_registry_and_exact_manifest_only() -> None:
    registry = json.loads(SOURCES.read_text(encoding="utf-8"))
    assert registry["policy"] == "SHA-pinned official manufacturer-primary sources only"
    assert len(registry["sources"]) == 9
    for source in registry["sources"]:
        assert urlparse(source["source_url"]).scheme == "https"
        snapshot = ROOT / source["snapshot_path"]
        assert snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source["snapshot_sha256"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["products"]) == 50
    assert {item["external_id"] for item in manifest["products"]} == {row["product_external_id"] for row in rows() if row["safe_to_apply"] == "true"}
    assert all(item["source_kind"] == "official_manufacturer_catalogue" for item in manifest["products"])


def test_exclusions_collision_guards_and_laravel_dry_run() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY_RUN.read_text(encoding="utf-8"))
    assert summary["previous_wave_exclusion"]["overlap_ids"] == []
    assert summary["scope_exclusion"] == {"automotive_rows": 0, "electronics_rows": 0}
    assert live["mode"] == "read_only" and live["database_mutations"] == 0 and live["collisions"] == []
    assert dry["mode"] == "dry_run" and dry["exit_code"] == 0 and dry["records"] == 50
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["commercial_fields_changed"] == 0 and dry["publication_fields_changed"] == 0
    assert dry["post_run_rows_with_manufacturer_or_mpn"] == 0 and dry["database_mutations"] == 0
