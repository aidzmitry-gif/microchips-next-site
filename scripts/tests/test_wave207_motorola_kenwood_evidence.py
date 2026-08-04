from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave207-motorola-kenwood-evidence.py"
EVIDENCE = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence-summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave207-motorola-kenwood-2026-07-29.json"
SOURCE_INDEX = ROOT / "docs/audits/sources/wave207-motorola-kenwood/snapshot-index.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_reproducible_and_final_dry_run_is_verified() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["input"]["rows"] == 104
    assert summary["input"]["manufacturer_counts"] == {"Kenwood": 30, "Motorola": 74}
    assert summary["wave206_exclusion"]["overlap_rows"] == 0
    assert summary["manifest"]["laravel_dry_run_verified"] is True


def test_partition_is_complete_and_fail_closed() -> None:
    evidence = rows()
    assert len(evidence) == 104
    assert {row["product_external_id"] for row in evidence}.__len__() == 104
    counts = {}
    for row in evidence:
        counts[row["partition"]] = counts.get(row["partition"], 0) + 1
    assert counts == {"no_evidence": 93, "exact_safe": 4, "conflict": 7}
    assert not [row for row in evidence if row["manufacturer_cluster"] == "Motorola" and row["safe_to_apply"] == "true"]


def test_exact_rows_are_primary_source_backed_and_manifest_only_contains_them() -> None:
    evidence = rows()
    safe = {row["product_external_id"]: row for row in evidence if row["safe_to_apply"] == "true"}
    assert set(safe) == {"bitrix:2597", "bitrix:2602", "bitrix:2608", "bitrix:2611"}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {row["external_id"] for row in manifest["products"]} == set(safe)
    for item in manifest["products"]:
        evidence_row = safe[item["external_id"]]
        assert item["source_kind"] == "official_manufacturer_accessory_catalogue"
        assert item["manufacturer"] == "Kenwood"
        assert item["mpn"] == evidence_row["replacement_mpn"]
        snapshot = (MANIFEST.parent / item["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert sha256(snapshot) == item["source_snapshot_sha256"]


def test_pinned_source_index_hashes_and_records_motorola_acquisition_holds() -> None:
    index = json.loads(SOURCE_INDEX.read_text(encoding="utf-8"))
    assert len(index["sources"]) == 2
    assert len(index["acquisition_failures"]) == 3
    assert all(row["source_id"].startswith("motorola_") for row in index["acquisition_failures"])
    for source in index["sources"]:
        snapshot = ROOT / source["snapshot_path"]
        text = ROOT / source["extracted_text_path"]
        assert sha256(snapshot) == source["snapshot_sha256"]
        assert sha256(text) == source["extracted_text_sha256"]


def test_conflicts_never_promote_identity() -> None:
    conflicts = [row for row in rows() if row["partition"] == "conflict"]
    assert len(conflicts) == 7
    assert all(row["manufacturer_cluster"] == "Kenwood" for row in conflicts)
    assert all(row["safe_to_apply"] == "false" for row in conflicts)
    assert all(not row["replacement_manufacturer"] and not row["replacement_mpn"] for row in conflicts)
    assert all(row["conflict_reason"] for row in conflicts)


def test_strict_identity_duplicate_groups_are_held() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    groups = summary["duplicate_guard"]["groups"]
    assert summary["duplicate_guard"]["strict_identity_groups"] == 9
    assert groups["Motorola:HNN9008A"] == ["bitrix:26135", "bitrix:26136", "bitrix:26137"]
    assert groups["Motorola:PMNN4021"] == ["bitrix:26288", "bitrix:2667"]
    duplicate_ids = {external_id for ids in groups.values() for external_id in ids}
    evidence = {row["product_external_id"]: row for row in rows()}
    assert all(evidence[external_id]["safe_to_apply"] == "false" for external_id in duplicate_ids)


def test_manifest_hash_matches_successful_laravel_dry_run() -> None:
    dry_run = json.loads((ROOT / "docs/audits/generated/wave207-laravel-dry-run.json").read_text(encoding="utf-8"))
    assert dry_run["exit_code"] == 0
    assert dry_run["mode"] == "dry_run"
    assert dry_run["records"] == 4
    assert dry_run["manifest_sha256"] == sha256(MANIFEST)
    assert dry_run["commercial_fields_changed"] == 0
    assert dry_run["publication_fields_changed"] == 0
