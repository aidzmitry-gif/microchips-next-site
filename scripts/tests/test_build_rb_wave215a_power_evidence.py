import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave215a-power-evidence.csv"
SUMMARY = GEN / "rb-wave215a-power-evidence.summary.json"
LIVE = GEN / "wave215a-power-live-identity-collisions.json"
DRY = GEN / "wave215a-power-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215a-power-2026-07-29.json"


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave215a_exact_scope_type_and_no_repeat_guards():
    evidence = rows(EVIDENCE)
    assert len(evidence) == len({row["product_external_id"] for row in evidence}) == 359
    assert Counter(row["source_cluster"] for row in evidence) == {"unresolved_other": 318, "APC": 36, "unresolved_industrial_cell": 5}
    assert Counter(row["factual_type"] for row in evidence) == {"ups_system": 314, "dc_dc_power_converter": 33, "ac_dc_power_supply": 12}
    assert all(row["factual_type"] not in {"battery", "electronics_component"} for row in evidence)
    assert len({row["family_group"] for row in evidence}) > 20
    assert all(row["family_group"] != "МПВ" or "МПВ" in row["model_candidate"] for row in evidence)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["scope"]["processed2500_overlap_ids"] == summary["scope"]["prior_evidence_overlap_ids"] == []


def test_wave215a_apc_evidence_is_exact_gate_and_all_large_families_hold():
    evidence = rows(EVIDENCE)
    apc = [row for row in evidence if row["source_cluster"] == "APC"]
    assert len(apc) == 36
    assert all(row["factual_type"] == "ups_system" and row["safe_to_apply"] == "false" for row in apc)
    assert all("no_exact_external_ID_name_model_match" in row["conflict_reason"] for row in apc)
    assert all(row["partition"] == "primary_source_batch_hold" and row["family_group"] for row in evidence)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["apc_pinned_evidence"]["exact_ID_name_model_matches"] == 0
    assert summary["apc_pinned_evidence"]["reused_source_records"] == 0


def test_wave215a_registry_live_and_laravel_dry_run_are_zero_apply():
    evidence = rows(EVIDENCE)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert all("batch_duplicate_external_ids" in row and "registry_model_candidate_external_ids" in row for row in evidence)
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 359 and live["database_mutations"] == 0
    assert dry["mode"] == "dry_run" and dry["apply_flag_used"] is False and dry["exit_code"] != 0
    assert "non-empty products list" in (dry["stdout"] + dry["stderr"])
    assert dry["database_mutations"] == dry["commercial_fields_changed"] == dry["publication_fields_changed"] == 0
    assert manifest["products"] == []
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert summary["policy"]["database_apply"] is False
