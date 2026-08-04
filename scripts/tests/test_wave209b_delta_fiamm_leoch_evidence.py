import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/audits/generated/wave209b-delta-fiamm-leoch-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave209b-delta-fiamm-leoch-summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave209b-delta-2026-07-29.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_scope_partition_and_automotive_gate():
    rows = read_csv(EVIDENCE)
    assert len(rows) == 136
    assert {row["manufacturer_cluster"] for row in rows} == {"Delta", "Fiamm", "Leoch"}
    assert {row["partition"] for row in rows} <= {"exact", "conflict", "no_evidence"}
    assert all(term not in row["name"].lower() for row in rows for term in ("автомоб", "стартер", "starter", "cranking"))


def test_exact_rows_have_pinned_primary_source_and_safe_manifest_is_subset():
    rows = read_csv(EVIDENCE)
    exact = [row for row in rows if row["partition"] == "exact"]
    assert len(exact) == 20
    for row in exact:
        path = ROOT / row["snapshot_path"]
        assert row["source_tier"] == "manufacturer_primary"
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["snapshot_sha256"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert {row["external_id"] for row in manifest["products"]} == {row["product_external_id"] for row in rows if row["safe_to_apply"] == "true"}
    assert all(row["source_kind"] == "official_manufacturer_product_page" for row in manifest["products"])


def test_known_conflicts_and_fail_closed_brands():
    rows = {row["product_external_id"]: row for row in read_csv(EVIDENCE)}
    assert rows["bitrix:20124"]["partition"] == "conflict"
    assert "45Ah" in rows["bitrix:20124"]["conflict_reason"]
    assert rows["bitrix:20138"]["partition"] == "conflict"
    assert "28Ah" in rows["bitrix:20138"]["conflict_reason"]
    assert all(row["partition"] == "no_evidence" and row["safe_to_apply"] == "false" for row in rows.values() if row["manufacturer_cluster"] in {"Fiamm", "Leoch"})


def test_summary_proves_zero_mutation_and_matching_dry_run():
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert data["wave206_exclusion"]["overlap_rows"] == 0
    assert data["scope_exclusion"]["automotive_or_starter_rows"] == 0
    assert data["live_collision_guard"]["candidate_rows_checked"] == 20
    assert data["manifest"]["laravel_dry_run_verified"] is True
    assert data["policy"]["database_mutations"] == 0
