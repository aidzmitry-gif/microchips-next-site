import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave243a-delta-new-product-evidence.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave243a-delta-evidence-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave243a-delta-evidence.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave243a-delta-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave243a-delta-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave243a-delta-new-product-evidence.md"
LARAVEL_DRY_RUN = ROOT / "docs/audits/generated/rb-wave243a-delta-description-laravel-dry-run.json"
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json"
REGISTRIES = (
    ROOT / "docs/audits/sources/wave243a-delta/registry.json",
    ROOT / "docs/audits/sources/wave243a-delta/datasheet-registry.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_builder() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True, text=True)


def rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave243a_is_deterministic_and_fail_closed() -> None:
    run_builder()
    outputs = (LEDGER, SUMMARY, IDENTITIES, DESCRIPTIONS, REPORT)
    first = {path: digest(path) for path in outputs}
    run_builder()
    assert first == {path: digest(path) for path in outputs}
    ledger = rows()
    assert len(ledger) == len({row["external_id"] for row in ledger}) == 80
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {"scope": 80, "pass": 6, "hold": 74}
    assert summary["hold_reasons"] == {
        "LEGACY_DUPLICATE_CANONICAL_OWNER": 23,
        "NO_NEW_OFFICIAL_EXACT_MODEL_SOURCE": 50,
        "TITLE_CAPACITY_CONFLICT": 1,
    }


def test_only_exact_supported_rows_enter_both_manifests() -> None:
    ledger = rows()
    passed = {row["external_id"] for row in ledger if row["decision"] == "PASS"}
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert len(passed) == len(identities) == len(descriptions) == 6
    assert {row["external_id"] for row in identities} == passed
    assert {row["external_id"] for row in descriptions} == passed
    for row in ledger:
        if row["decision"] == "PASS":
            assert row["source_voltage_v"] == "12"
            assert row["source_capacity_ah"]
            assert row["source_technology"] == "AGM"
            assert row["source_url"] and row["datasheet_url"]
    conflict = next(row for row in ledger if row["external_id"] == "bitrix:1448")
    assert conflict["decision"] == "HOLD"
    assert conflict["source_capacity_ah"] == "12"
    assert conflict["hold_reason"] == "TITLE_CAPACITY_CONFLICT"


def test_all_product_pages_and_datasheets_are_new_and_pinned() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {item["value"] for item in exclusions["source_urls"]}
    prior_hashes = {item["value"] for item in exclusions["snapshot_sha256"]}
    assert len(exclusions["scanned_files"]) == 345
    for registry_path in REGISTRIES:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        assert len(registry["sources"]) == 7
        for source in registry["sources"]:
            snapshot = ROOT / source["snapshot_path"]
            assert source["source_url"] not in prior_urls
            assert source["snapshot_sha256"] not in prior_hashes
            assert digest(snapshot) == source["snapshot_sha256"]


def test_builder_is_offline_and_manifests_use_stageable_contract() -> None:
    source = BUILDER.read_text(encoding="utf-8")
    assert "urllib" not in source and "requests" not in source
    payload = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))
    assert payload["locale"] == "ru-BY" and payload["purpose"]
    for row in payload["products"]:
        assert row["manufacturer_primary"] is True
        assert row["source_kind"] == "official_manufacturer_product_page"
        assert set(row) == {
            "external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url",
            "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary",
            "evidence_scope", "checked_at",
        }
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    assert dry_run["manifest_sha256"] == digest(DESCRIPTIONS)
    assert dry_run["records"] == 6 and dry_run["exit_code"] == 0
    assert dry_run["apply_flag_used"] is False and dry_run["persisted_description_drafts"] == 0
