from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave204-verified-oem-identities.py"
OUTPUT = ROOT / "docs/imports/rb-verified-oem-identities-wave204-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/wave204-verified-oem-identities-summary.json"

EXACT_IDS = {
    "bitrix:2239",
    "bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397",
    "bitrix:20045", "bitrix:20049", "bitrix:20050", "bitrix:20059",
    "bitrix:20060", "bitrix:20061", "bitrix:20071", "bitrix:20073", "bitrix:20075",
}
ELIGIBLE_IDS = {
    "bitrix:2394", "bitrix:2395", "bitrix:2396", "bitrix:2397",
    "bitrix:20045", "bitrix:20071", "bitrix:20073", "bitrix:20075",
}
HELD_IDS = EXACT_IDS - ELIGIBLE_IDS
ALLOWED_SOURCE_KINDS = {
    "official_manufacturer_catalogue",
    "official_manufacturer_accessory_catalogue",
    "official_manufacturer_product_page",
    "official_manufacturer_service_document",
}


def load_module():
    spec = importlib.util.spec_from_file_location("wave204_verified_oem_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_is_reproducible_and_checks_41_34_31_union() -> None:
    command = [sys.executable, str(BUILDER), "--skip-upstream-build"]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    first_manifest = OUTPUT.read_bytes()
    first_summary = SUMMARY.read_bytes()
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    assert OUTPUT.read_bytes() == first_manifest
    assert SUMMARY.read_bytes() == first_summary

    module = load_module()
    partitions = module.validate_union()
    assert {key: len(rows) for key, rows in partitions.items()} == {
        "radio": 41, "industrial": 34, "remote": 31,
    }
    sets = [set(rows) for rows in partitions.values()]
    assert len(set().union(*sets)) == 106
    assert all(not sets[left] & sets[right] for left in range(3) for right in range(left + 1, 3))


def test_evidence_exact_is_separate_from_apply_eligibility() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8-sig"))
    assert summary["evidence_exact"]["rows"] == 14
    assert set(summary["evidence_exact"]["external_ids"]) == EXACT_IDS
    assert summary["apply_eligible"]["rows"] == 8
    assert set(summary["apply_eligible"]["external_ids"]) == ELIGIBLE_IDS
    assert {row["external_id"] for row in manifest["products"]} == ELIGIBLE_IDS
    assert summary["holds"]["rows"] == 6
    assert {row["external_id"] for row in summary["holds"]["products"]} == HELD_IDS
    assert all(row["reason"] == "official_part_not_pinned_in_legacy_name" for row in summary["holds"]["products"])


def test_name_contains_gate_is_bounded_and_not_weakened() -> None:
    module = load_module()
    assert module.name_contains("Аккумулятор Alinco EBP-50N", "Alinco")
    assert module.name_contains("Аккумулятор Alinco EBP-50N", "EBP-50N")
    assert module.name_contains("Аккумулятор AUTEC AIRBM3V7L", "AIRBM3V7L")
    assert not module.name_contains("Батарея Ni-Mh ВТ06К- АТЕХ", "Danfoss")
    assert not module.name_contains("Батарея Ni-Mh ВТ06К- АТЕХ", "BT06K ATEX")
    assert not module.name_contains("Аккумулятор ELCA PINC-07MH", "0401BA000112")
    assert not module.name_contains("Аккумулятор HIAB XSDRIVE 4000", "3786692B")
    assert not module.name_contains("Аккумулятор AUTEC MBM06MH", "MBM06")
    assert not module.name_contains("Аккумулятор XAUTEC MBM06MH", "AUTEC")


def test_manifest_matches_unchanged_laravel_contract() -> None:
    manifest = json.loads(OUTPUT.read_text(encoding="utf-8-sig"))
    assert set(manifest) == {"schema_version", "site_key", "products"}
    assert manifest["schema_version"] == 1
    assert manifest["site_key"] == "microchips-by"
    assert len(manifest["products"]) == 8
    expected_fields = {
        "external_id", "current_name", "manufacturer", "mpn", "source_url",
        "source_kind", "source_publisher", "checked_at", "product_type",
        "source_snapshot_path", "source_snapshot_sha256",
    }
    normalized_mpns = set()
    for row in manifest["products"]:
        assert set(row) == expected_fields
        assert all(isinstance(value, str) and value.strip() for value in row.values())
        assert row["source_kind"] in ALLOWED_SOURCE_KINDS
        assert row["source_url"].startswith("https://")
        assert row["source_snapshot_path"].startswith("../audits/sources/")
        assert not Path(row["source_snapshot_path"]).is_absolute()
        snapshot = (OUTPUT.parent / row["source_snapshot_path"]).resolve()
        assert snapshot.is_relative_to(ROOT.resolve()) and snapshot.is_file()
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["source_snapshot_sha256"]
        normalized_mpns.add("".join(character for character in row["mpn"].casefold() if character.isalnum()))
    assert len(normalized_mpns) == 8


def test_all_14_exact_rows_have_hash_and_exact_token_proof() -> None:
    module = load_module()
    outputs = module.validate_union()
    exact = module.collect_exact(outputs)
    assert len(exact) == 14
    assert {row["external_id"] for row in exact} == EXACT_IDS
    assert all(row["required_exact_tokens"] for row in exact)
    assert all(len(row["snapshot_sha256"]) == 64 for row in exact)
    assert all((ROOT / row["snapshot_repo_path"]).is_file() for row in exact)

    snapshot = ROOT / "docs/audits/sources/wave204-radio/alinco-handheld-accessories-2006-snapshot.pdf"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        module.validate_snapshot(snapshot, "0" * 64, ("EBP-50N",))
    with pytest.raises(ValueError, match="lacks exact tokens"):
        module.validate_snapshot(snapshot, hashlib.sha256(snapshot.read_bytes()).hexdigest(), ("TOKEN-NOT-PRESENT",))


def test_summary_reconciles_manifest_and_records_zero_mutation() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert summary["input_union"] == {
        "radio_rows": 41,
        "industrial_rows": 34,
        "remote_rows": 31,
        "union_rows": 106,
        "pairwise_overlap_rows": 0,
    }
    assert summary["apply_eligible"]["manifest_sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["source_validation"]["snapshots_sha256_verified"] == 14
    assert summary["source_validation"]["exact_token_sets_verified"] == 14
    assert summary["source_validation"]["relative_manifest_snapshot_paths"] == 8
    assert summary["policy"] == {
        "laravel_name_contains_gate_weakened": False,
        "official_exact_is_not_automatically_apply_eligible": True,
        "database_mutations": 0,
    }
