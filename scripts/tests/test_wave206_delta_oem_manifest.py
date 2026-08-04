from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave206-delta-oem-manifest.py"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave206-delta-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-verified-oem-identities-wave206-delta.summary.json"
SPLIT_DIR = ROOT / "docs/audits/generated/rb-wave206-delta-oem-candidates"
COLLISIONS = ROOT / "docs/audits/evidence/wave206-delta-current-db-collisions.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", value or "").casefold())


def test_manifest_builder_is_deterministic_and_emits_18_collision_free_rows() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = digest(MANIFEST)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert digest(MANIFEST) == first
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert len(manifest["products"]) == 18
    assert len({row["external_id"] for row in manifest["products"]}) == 18
    assert len({normalized(row["mpn"]) for row in manifest["products"]}) == 18
    split = sorted(SPLIT_DIR.glob("*.json"))
    assert len(split) == 18
    assert all(len(json.loads(path.read_text(encoding="utf-8"))["products"]) == 1 for path in split)


def test_every_manifest_row_is_literal_bounded_and_snapshot_pinned() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for row in manifest["products"]:
        assert row["manufacturer"] == "Delta"
        assert normalized("Delta") in normalized(row["current_name"])
        assert normalized(row["mpn"]) in normalized(row["current_name"])
        assert row["source_url"].startswith("https://")
        assert "delta-batt.com" in row["source_url"]
        assert row["source_kind"] == "official_manufacturer_product_page"
        snapshot = (MANIFEST.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_file()
        assert digest(snapshot) == row["source_snapshot_sha256"]


def test_manifest_has_no_commercial_or_publication_claims_and_summary_records_holds() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    forbidden = {"price", "currency", "availability", "stock", "is_published", "schema", "offer"}
    assert all(forbidden.isdisjoint(row) for row in manifest["products"])
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["manifest"]["rows"] == 18
    assert summary["holds"] == {"rows": 44, "research_conflict": 19, "no_evidence": 16, "compatibility_only": 0, "current_db_identity_collision": 9}
    assert summary["laravel_dry_run"]["records"] == 18
    assert summary["laravel_dry_run"]["manifest_sha256"] == digest(MANIFEST)
    assert summary["laravel_dry_run"]["exit_code"] == 0
    assert summary["gate"]["database_mutations"] == 0


def test_all_current_db_collisions_are_pinned_and_excluded() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    collisions = json.loads(COLLISIONS.read_text(encoding="utf-8"))
    collision_ids = {row["candidate_external_id"] for row in collisions["collisions"]}
    assert collision_ids == {
        "bitrix:1400", "bitrix:1401", "bitrix:1419", "bitrix:1421", "bitrix:1475",
        "bitrix:1476", "bitrix:1481", "bitrix:1504", "bitrix:1556",
    }
    assert collision_ids.isdisjoint(row["external_id"] for row in manifest["products"])
    assert all(row["conflicting_external_id"] and row["normalized_identifier"] for row in collisions["collisions"])
