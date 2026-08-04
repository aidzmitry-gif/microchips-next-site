from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave217c-replacement-radio-industrial-evidence.csv"
SUMMARY = GEN / "rb-wave217c-replacement-radio-industrial-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave217c-replacement-radio-industrial-2026-07-29.json"
LIVE = GEN / "wave217c-replacement-radio-industrial-live-identity-collisions.json"
DRY = GEN / "wave217c-replacement-radio-industrial-laravel-dry-run.json"


def rows() -> list[dict[str, str]]:
    with EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave217c_exact_49_row_scope_and_context_extraction() -> None:
    data = rows()
    assert len(data) == len({row["product_external_id"] for row in data}) == 49
    assert Counter(row["lane"] for row in data) == {"replacement_context_hold": 40, "at_radio_charger": 6, "industrial_cell": 3}
    assert {row["category_external_id"] for row in data if row["lane"] == "at_radio_charger"} == {"seo:chargers"}
    assert {row["category_external_id"] for row in data if row["lane"] == "industrial_cell"} == {"seo:batteries-industrial"}
    assert all(row["equipment_or_device_context"] and row["title_series_or_model_candidate"] for row in data)
    assert all(row["safe_to_apply"] == "false" for row in data)


def test_wave217c_partition_and_fail_closed_db_guards() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert summary["wave217_partition"] == {"a_unresolved_other": 395, "b_claimed_manufacturer": 56, "c_replacement_radio_industrial": 49, "disjoint_union_rows": 500, "pairwise_overlap_rows": 0}
    assert summary["processed3000_overlap_ids"] == []
    assert summary["scope_exclusion"] == {"automotive_rows": 0, "electronics_rows": 0}
    assert summary["target"]["manufacturer_clusters"] == {"AT radio packs": 6, "unresolved_industrial_cell": 3, "unresolved_replacement": 40}
    assert manifest["products"] == []
    assert live["mode"] == "read_only" and live["candidate_rows_checked"] == 49 and live["database_mutations"] == 0
    assert dry["exit_code"] != 0 and dry["apply_flag_used"] is False and "non-empty products list" in (dry["stdout"] + dry["stderr"])
    assert dry["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
