from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/audits/generated/rb-wave213c-industrial-cell-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave213c-industrial-cell-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave213c-industrial-2026-07-29.json"
LIVE = ROOT / "docs/audits/generated/wave213c-industrial-live-identity-collisions.json"
DRY = ROOT / "docs/audits/generated/wave213c-industrial-laravel-dry-run.json"


def test_wave213c_is_exactly_the_five_unresolved_industrial_cells() -> None:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["product_external_id"] for row in rows] == ["bitrix:11348", "bitrix:11349", "bitrix:11351", "bitrix:11426", "bitrix:1688"]
    assert {row["partition"] for row in rows} == {"no_evidence"}
    assert {row["safe_to_apply"] for row in rows} == {"false"}
    assert rows[2]["official_source_url"].startswith("https://www.flukebiomedical.com/")


def test_wave213c_exclusion_db_guard_and_empty_exact_safe_manifest() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert summary["processed2000_overlap_ids"] == []
    assert summary["wave213_partition"] == {"a_unresolved_replacement": 274, "b_unresolved_other_power_systems": 221, "c_unresolved_industrial_cell": 5, "disjoint_union_rows": 500, "pairwise_overlap_rows": 0}
    assert summary["scope_exclusion"] == {"automotive_rows": 0, "electronics_rows": 0}
    assert summary["partition_counts"] == {"no_evidence": 5, "exact_safe": 0}
    assert manifest["products"] == []
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert dry["exit_code"] != 0 and "non-empty products list" in (dry["stdout"] + dry["stderr"])
    assert dry["database_mutations"] == live["database_mutations"] == 0
