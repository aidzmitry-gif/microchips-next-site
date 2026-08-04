import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "scripts/build-rb-wave242-delta-hold-research.py"
ACQUIRER = ROOT / "scripts/acquire-rb-wave242-delta-primary-sources.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave242-delta-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave242-delta-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave242-delta-hold-research.md"
REGISTRY = ROOT / "docs/audits/sources/wave242-delta/registry.json"
LARAVEL_DRY_RUN = ROOT / "docs/audits/generated/rb-wave242-delta-description-laravel-dry-run.json"
OUTPUTS = (LEDGER, SUMMARY, IDENTITIES, DESCRIPTIONS, REPORT)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_builder() -> None:
    subprocess.run([sys.executable, str(BUILDER)], cwd=ROOT, check=True, capture_output=True, text=True)


def ledger_rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module", autouse=True)
def build_once() -> None:
    run_builder()


def test_builder_is_deterministic_and_processes_all_136_once():
    first = {path: digest(path) for path in OUTPUTS}
    run_builder()
    assert first == {path: digest(path) for path in OUTPUTS}
    rows = ledger_rows()
    assert len(rows) == 136
    assert len({row["external_id"] for row in rows}) == 136
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["coverage"] == {"scope": 136, "pass": 59, "hold": 77}
    assert summary["hold_reasons"] == {
        "LIVE_DUPLICATE_OWNERSHIP_CONFLICT": 23,
        "NO_NEW_OFFICIAL_EXACT_OFFERED_MODEL": 61,
        "TITLE_CAPACITY_CONFLICT": 1,
    }
    assert summary["description_coverage"] == {"scope": 136, "pass": 56, "hold": 80}
    assert summary["description_hold_reasons"] == {
        "LIVE_DUPLICATE_OWNERSHIP_CONFLICT": 23,
        "NO_NEW_OFFICIAL_EXACT_OFFERED_MODEL": 61,
        "NO_SOURCE_SUPPORTED_TECHNOLOGY": 5,
        "TITLE_CAPACITY_CONFLICT": 1,
    }


def test_pass_manifests_are_exactly_the_safe_59_rows():
    rows = ledger_rows()
    identity_passed = {row["external_id"] for row in rows if row["decision"] == "PASS"}
    description_passed = {row["external_id"] for row in rows if row["description_decision"] == "PASS"}
    assert len(identity_passed) == 59
    assert len(description_passed) == 56
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    description_payload = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))
    descriptions = description_payload["products"]
    assert description_payload["locale"] == "ru-BY"
    assert description_payload["purpose"]
    assert {row["external_id"] for row in identities} == identity_passed
    assert {row["external_id"] for row in descriptions} == description_passed
    assert digest(IDENTITIES) == "277ed4896e6d46c94d1dae66a92e22ffb4ff1fb9bfBCD046d38177f7b61ee9b7".lower()
    for row in rows:
        if row["decision"] != "PASS":
            continue
        assert not row["hold_reason"]
        assert not row["live_duplicate_owner_external_ids"]
        assert row["source_offered_model"]
        assert row["title_capacity_ah"] == row["source_capacity_ah"]
        if row["title_voltage_v"]:
            assert row["title_voltage_v"] == row["source_voltage_v"]
    for row in identities:
        assert row["manufacturer"] == "Delta"
        assert row["mpn"]
        assert row["source_kind"] == "official_manufacturer_catalogue"
        assert digest((IDENTITIES.parent / row["source_snapshot_path"]).resolve()) == row["source_snapshot_sha256"]
    for row in descriptions:
        assert row["manufacturer_primary"] is True
        assert row["source_tier"] == "manufacturer_primary"
        assert row["technical_attributes"]["Модель"] == row["model_core"]
        assert row["technology"] == "AGM"
        assert set(row) == {
            "external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url",
            "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary",
            "evidence_scope", "checked_at",
        }


def test_all_23_duplicate_owners_and_the_capacity_conflict_are_held():
    rows = ledger_rows()
    duplicate_rows = [row for row in rows if row["live_duplicate_owner_external_ids"]]
    assert len(duplicate_rows) == 23
    assert all(row["decision"] == "HOLD" for row in duplicate_rows)
    conflict = next(row for row in rows if row["external_id"] == "bitrix:1448")
    assert conflict["decision"] == "HOLD"
    assert conflict["mpn"] == "CT 1212.2"
    assert conflict["title_capacity_ah"] == "14"
    assert conflict["source_capacity_ah"] == "12"
    assert conflict["hold_reason"] == "TITLE_CAPACITY_CONFLICT"


def test_new_sources_are_official_pinned_and_do_not_repeat_wave233a():
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert len(payload["sources"]) == 10
    prior = list(csv.DictReader((ROOT / "docs/audits/generated/rb-wave233a-delta-identity-ledger.csv").open(
        encoding="utf-8-sig", newline="")))
    old_hashes = {row["source_snapshot_sha256"] for row in prior if row["source_snapshot_sha256"]}
    old_urls = {row["source_url"] for row in prior if row["source_url"]}
    registered = {ROOT / source["snapshot_path"] for source in payload["sources"]}
    disk = set((ROOT / "docs/audits/sources/wave242-delta").glob("*.html"))
    assert disk == registered
    for source in payload["sources"]:
        assert source["source_url"].startswith(("https://delta-batt.com/", "https://www.delta-batt.com/"))
        assert digest(ROOT / source["snapshot_path"]) == source["snapshot_sha256"]
        assert source["snapshot_sha256"] not in old_hashes
        assert source["source_url"] not in old_urls


def test_generated_text_is_clean_utf8_and_builder_is_offline():
    for path in (*OUTPUTS, REGISTRY, LARAVEL_DRY_RUN):
        text = path.read_bytes().decode("utf-8-sig")
        assert "\ufffd" not in text, path
        assert "РњРѕРґРµР»СЊ" not in text, path
    builder_source = BUILDER.read_text(encoding="utf-8")
    assert "urllib" not in builder_source
    assert "requests" not in builder_source
    assert "artisan" not in builder_source
    assert "database_operations\": 0" in builder_source
    acquirer_source = ACQUIRER.read_text(encoding="utf-8")
    assert "ALLOWED_HOSTS" in acquirer_source
    assert "urllib.request" in acquirer_source


def test_real_laravel_dry_run_is_pinned_to_the_final_stageable_manifest():
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    assert dry_run["actual_laravel_command_executed"] is True
    assert dry_run["manifest_sha256"] == digest(DESCRIPTIONS)
    assert dry_run["records"] == 56
    assert dry_run["exit_code"] == 0
    assert dry_run["apply_flag_used"] is False
    assert dry_run["persisted_description_drafts"] == 0
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["laravel_dry_run"]["sha256"] == digest(LARAVEL_DRY_RUN)
