import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave241c-description-image-no-repeat.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave241c-description-image-no-repeat-ledger.csv"
SKIPS = ROOT / "docs/audits/generated/rb-wave241c-reviewed-identity-skips.csv"
ACTIONABLE = ROOT / "docs/audits/generated/rb-wave241c-new-description-actionable.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave241c-description-image-no-repeat.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave241c-description-image-no-repeat.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_builder() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)


def test_builder_is_deterministic_and_partitions_all_502_rows():
    run_builder()
    first = {path: digest(path) for path in (LEDGER, SKIPS, ACTIONABLE, SUMMARY, REPORT)}
    run_builder()
    assert first == {path: digest(path) for path in first}

    ledger, skips, actionable = rows(LEDGER), rows(SKIPS), rows(ACTIONABLE)
    assert len(ledger) == 502
    assert len(skips) == 458
    assert len(actionable) == 44
    skip_ids = {row["product_external_id"] for row in skips}
    actionable_ids = {row["product_external_id"] for row in actionable}
    assert skip_ids.isdisjoint(actionable_ids)
    assert skip_ids | actionable_ids == {row["product_external_id"] for row in ledger}


def test_every_blank_manufacturer_is_an_exact_prior_hold_not_new_research():
    run_builder()
    skips = rows(SKIPS)
    assert all(not row["manufacturer"] and not row["mpn"] for row in skips)
    assert all(row["disposition"] == "SKIP_REVIEWED_IDENTITY_HOLD" for row in skips)
    assert all(row["prior_decision"] == "HOLD" for row in skips)
    assert all(row["evidence_match"] == "exact_external_id+normalized_exact_title" for row in skips)
    assert all(row["next_action"].startswith("do_not_repeat_research") for row in skips)
    assert Counter(row["evidence_path"] for row in skips) == {
        "docs/audits/generated/rb-wave233a-delta-identity-ledger.csv": 136,
        "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv": 27,
        "docs/audits/generated/rb-wave237-fiamm-authorized-identity-ledger.csv": 29,
        "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity-ledger.csv": 131,
        "docs/audits/generated/rb-wave234a-panasonic-mnb-identity-ledger.csv": 56,
        "docs/audits/generated/rb-wave234b-apc-enersys-identity-ledger.csv": 34,
        "docs/audits/generated/rb-wave234c-general-security-identity-ledger.csv": 8,
        "docs/audits/generated/rb-wave234c-residual-identity-holds.csv": 37,
    }


def test_actionable_rows_have_exact_pinned_identity_but_no_replayable_description():
    run_builder()
    actionable = rows(ACTIONABLE)
    assert Counter(row["manufacturer"] for row in actionable) == {
        "EnerSys": 15,
        "Sonnenschein": 8,
        "MNB": 8,
        "APC": 5,
        "Panasonic": 4,
        "Ventura": 4,
    }
    for row in actionable:
        assert row["manufacturer"] and row["mpn"]
        assert row["disposition"] == "NEW_DESCRIPTION_ACTIONABLE"
        assert row["prior_decision"] == "EXACT_PRIMARY_IDENTITY_PASS"
        assert row["source_tier"] in {"manufacturer_primary", "manufacturer_catalogue_primary"}
        assert row["source_url"].startswith("https://")
        assert len(row["source_snapshot_sha256"]) == 64
        assert "no prior exact source-backed description manifest" in row["missing_evidence"]

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["scope"]["prior_exact_description_manifest_matches"] == 0
    assert summary["scope"]["description_manifest_prepared"] is False


def test_summary_pins_outputs_and_declares_zero_side_effects():
    run_builder()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["input"]["description_false_image_false_rows"] == 502
    assert summary["scope"]["reviewed_identity_holds_skipped"] == 458
    assert summary["scope"]["genuinely_new_description_actionable"] == 44
    for key, path in (("ledger", LEDGER), ("skips", SKIPS), ("actionable", ACTIONABLE)):
        assert summary["outputs"][key]["sha256"] == digest(path)
    assert summary["database_queries"] == 0
    assert summary["database_mutations"] == 0
    assert summary["network_requests"] == 0
    assert summary["apply_performed"] is False
