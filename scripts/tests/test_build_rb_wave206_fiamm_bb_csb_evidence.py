import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave206-fiamm-bb-csb-evidence.py"
OUTPUT = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.summary.json"


def run_builder():
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    with OUTPUT.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows, json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_partition_is_complete_and_fail_closed():
    rows, summary = run_builder()
    assert len(rows) == 38
    assert summary["brand_counts"] == {"B.B. Battery": 7, "CSB": 1, "Fiamm": 30}
    assert summary["partition_counts"] == {
        "compatibility": 11,
        "conflict": 3,
        "exact": 23,
        "no_evidence": 1,
    }


def test_only_primary_bb_exact_rows_are_apply_safe():
    rows, summary = run_builder()
    safe = {row["product_external_id"] for row in rows if row["safe_to_apply"] == "true"}
    assert safe == {"bitrix:1519", "bitrix:1526", "bitrix:1565", "bitrix:1587", "bitrix:1593"}
    output_order = [row["product_external_id"] for row in rows if row["safe_to_apply"] == "true"]
    assert summary["safe_to_apply"] == {"rows": 5, "external_ids": output_order}
    assert all(row["source_tier"] == "manufacturer_primary" for row in rows if row["safe_to_apply"] == "true")


def test_known_claim_conflicts_and_variant_holds_are_not_apply_safe():
    rows, _ = run_builder()
    by_id = {row["product_external_id"]: row for row in rows}
    assert {by_id[key]["partition"] for key in ("bitrix:1427", "bitrix:1444", "bitrix:1462")} == {"conflict"}
    assert by_id["bitrix:1418"]["partition"] == "compatibility"
    assert by_id["bitrix:1594"]["partition"] == "compatibility"
    assert by_id["bitrix:1463"]["partition"] == "no_evidence"
    assert all(by_id[key]["safe_to_apply"] == "false" for key in ("bitrix:1427", "bitrix:1444", "bitrix:1462", "bitrix:1418", "bitrix:1594", "bitrix:1463"))


def test_snapshots_are_hash_pinned_and_tokens_were_validated():
    rows, summary = run_builder()
    assert len(summary["sources"]) == 11
    assert all(len(source["sha256"]) == 64 for source in summary["sources"].values())
    assert all(row["snapshot_sha256"] and row["required_tokens"] for row in rows if row["partition"] != "no_evidence")
    assert summary["strict_duplicates"] == {"clusters": 1}
    by_id = {row["product_external_id"]: row for row in rows}
    assert by_id["bitrix:1590"]["duplicate_review"] == "strict_duplicate_hold:КА-00003582"
