from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave203-verified-oem-identities.py"
OUTPUT = ROOT / "docs/imports/rb-verified-oem-identities-wave203-2026-07-29.json"
EXPECTED_IDS = {"bitrix:12398", "bitrix:12204", "bitrix:12304", "bitrix:12329"}
ALLOWED_SOURCE_KINDS = {
    "official_manufacturer_catalogue",
    "official_manufacturer_accessory_catalogue",
    "official_manufacturer_product_page",
    "official_manufacturer_service_document",
}


def load_module():
    spec = importlib.util.spec_from_file_location("wave203_verified_oem_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_is_reproducible_and_checks_143_row_union() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True, text=True)
    first = OUTPUT.read_bytes()
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True, text=True)
    assert OUTPUT.read_bytes() == first
    module = load_module()
    partitions = module.validate_union()
    assert {name: len(rows) for name, rows in partitions.items()} == {"pos": 42, "capture": 74, "remaining": 27}
    assert len(set().union(*(set(rows) for rows in partitions.values()))) == 143


def test_manifest_matches_strengthened_laravel_contract() -> None:
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8-sig"))
    assert set(manifest) == {"schema_version", "site_key", "products"}
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert len(manifest["products"]) == 4
    assert {row["external_id"] for row in manifest["products"]} == EXPECTED_IDS
    assert len({row["mpn"].casefold() for row in manifest["products"]}) == 4
    expected_fields = {
        "external_id", "current_name", "manufacturer", "mpn", "source_url",
        "source_kind", "source_publisher", "checked_at", "product_type",
        "source_snapshot_path", "source_snapshot_sha256",
    }
    for row in manifest["products"]:
        assert set(row) == expected_fields
        assert all(isinstance(value, str) and value.strip() for value in row.values())
        assert row["source_kind"] in ALLOWED_SOURCE_KINDS
        assert row["source_url"].startswith("https://")
        assert row["source_snapshot_path"].startswith("../audits/sources/")
        snapshot = (OUTPUT.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_relative_to(ROOT.resolve()) and snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]


def test_snapshot_validation_fails_closed_on_hash_or_token_drift() -> None:
    module = load_module()
    snapshot = ROOT / "docs/audits/sources/wave203-remaining/cino-f680bt-accessories-2026-07-29.html"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        module.validate_snapshot(snapshot, "0" * 64, ("EXACT-MPN",))
    with pytest.raises(ValueError, match="lacks exact tokens"):
        module.validate_snapshot(
            snapshot,
            hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            ("TOKEN-THAT-DOES-NOT-EXIST",),
        )


def test_exact_rows_are_only_the_four_pinned_pos_and_remaining_records() -> None:
    module = load_module()
    partitions = module.validate_union()
    safe = {
        row["product_external_id"]
        for rows in partitions.values()
        for row in rows.values()
        if row.get("safe_to_apply") == "true"
    }
    assert safe == EXPECTED_IDS
    assert all(external_id not in partitions["capture"] or partitions["capture"][external_id]["safe_to_apply"] == "false" for external_id in safe)
