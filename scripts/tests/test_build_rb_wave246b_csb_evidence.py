import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/audits/generated/rb-wave246b-csb-evidence-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246b-csb.summary.json"
PRIOR = ROOT / "docs/audits/generated/rb-wave246b-csb-prior-evidence-index.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-2026-07-30.json"
BITRIX = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-bitrix-dry-run-2026-07-30.json"
ACTIVE = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-active-1c-dry-run-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave246b-csb-2026-07-30.json"
DRY = ROOT / "docs/audits/generated/rb-wave246b-csb-laravel-dry-runs.json"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def products(path):
    return json.loads(path.read_text(encoding="utf-8"))["products"]


def test_builder_is_reproducible_and_scope_is_exactly_92():
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (LEDGER, IDENTITIES, BITRIX, ACTIVE, DESCRIPTIONS)}
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave246b-csb-evidence.py")], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert after == before
    ledger = rows(LEDGER)
    assert len(ledger) == 92
    assert len({row["external_id"] for row in ledger}) == 92
    assert all(row["manufacturer"] == "CSB" for row in ledger)


def test_live_owner_guard_holds_only_four_exact_duplicates():
    ledger = {row["external_id"]: row for row in rows(LEDGER)}
    hold_ids = {external_id for external_id, row in ledger.items() if row["decision"] == "HOLD"}
    assert hold_ids == {"bitrix:2829", "bitrix:2912", "bitrix:3027", "bitrix:754"}
    assert all(ledger[external_id]["hold_reason"] == "EXACT_NON_TARGET_OWNER_EXISTS" for external_id in hold_ids)
    assert sum(row["decision"] == "PASS" for row in ledger.values()) == 88


def test_f2_variants_are_identity_sensitive_and_catalogue_backed():
    ledger = {row["mpn"]: row for row in rows(LEDGER)}
    variants = {"GP645 F2", "GP6120 F2", "GP1272 F2", "GP12120 F2"}
    assert all(ledger[mpn]["terminal_variant_check"] == "PASS_EXACT_F2_IN_MODEL_TABLE" for mpn in variants)
    assert all(ledger[mpn]["catalogue_page"] == "3" for mpn in variants)
    assert ledger["GP1272 F2"]["decision"] == "HOLD"
    assert all(ledger[mpn]["decision"] == "PASS" for mpn in variants - {"GP1272 F2"})


def test_only_pass_rows_enter_identity_and_description_manifests():
    ledger = rows(LEDGER)
    pass_ids = {row["external_id"] for row in ledger if row["decision"] == "PASS"}
    identities = products(IDENTITIES)
    descriptions = products(DESCRIPTIONS)
    assert len(identities) == len(descriptions) == 88
    assert {row["external_id"] for row in identities} == pass_ids
    assert {row["external_id"] for row in descriptions} == pass_ids
    assert all(row["identity_scope"] == row["evidence_scope"] == "model_core" for row in descriptions)
    assert all(row["model_core"] == row["technical_attributes"]["Модель"] for row in descriptions)
    assert all(set(row["technical_attributes"]) == {"Модель", "Серия", "Технология"} for row in descriptions)


def test_identity_command_subsets_and_real_dry_run_invariants():
    assert json.loads(BITRIX.read_text(encoding="utf-8"))["target_kind"] == "bitrix_draft"
    assert json.loads(ACTIVE.read_text(encoding="utf-8"))["target_kind"] == "active_1c"
    assert len(products(BITRIX)) == 12
    assert len(products(ACTIVE)) == 3
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    assert dry["actual_laravel_commands_executed"] is True
    assert dry["identity"]["records_checked"] == 15
    assert dry["identity"]["existing_manufacturer_draft_not_supported_target_kind"] == 73
    assert dry["description"]["records"] == 88
    assert {key: dry["description"][key] for key in ("created", "refreshed", "unchanged", "published")} == {"created": 0, "refreshed": 88, "unchanged": 0, "published": 0}
    assert isinstance(dry["description"]["import_run_id"], int)
    assert dry["invariants"]["apply_flag_used"] is False
    assert dry["invariants"]["commercial_fields_changed"] == 0
    assert dry["invariants"]["publication_fields_changed"] == 0
    assert dry["invariants"]["domain_record_mutations"] == 0
    assert dry["invariants"]["dry_run_audit_import_runs_created_by_final_runner"] == 1


def test_prior_research_is_fully_reused_and_media_is_closed():
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert prior["scope_rows"] == prior["covered_rows"] == 92
    assert prior["new_row_research_performed"] == 0
    assert all(row["evidence_files"] for row in prior["coverage"])
    assert summary["decisions"] == {"HOLD": 4, "PASS": 88}
    assert summary["manifests"]["media"] == 0
    assert summary["safety"]["network_research_calls"] == 0
    assert summary["safety"]["apply_performed"] is False
    assert not list((ROOT / "docs/imports").glob("*wave246b*media*.json"))
