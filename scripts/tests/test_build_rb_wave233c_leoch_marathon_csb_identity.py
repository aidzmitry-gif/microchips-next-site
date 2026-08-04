from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave233c-leoch-marathon-csb-identity.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave233c-leoch-marathon-csb-2026-07-29.json"


def rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave233c_is_deterministic_and_complete() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    before = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    after = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert before == after
    data = rows()
    assert len(data) == 131
    assert Counter(row["manufacturer_candidate"] for row in data) == {"CSB": 32, "Leoch": 50, "Marathon": 49}
    assert len({row["external_id"] for row in data}) == 131


def test_wave233c_is_fail_closed_on_exact_source_and_collision_rules() -> None:
    data = rows()
    by_id = {row["external_id"]: row for row in data}
    assert all(row["safe_to_apply"] == "false" for row in data)
    assert by_id["bitrix:1418"]["partition"] == "hold_exact_suffix_conflict"
    assert by_id["bitrix:1418"]["mpn_candidate"] == "HRL12390W FR"
    assert by_id["bitrix:25828"]["collision_external_ids"] == "bitrix:25830"
    assert by_id["bitrix:25830"]["collision_external_ids"] == "bitrix:25828"
    assert all(not row["source_sku"] and not row["normalized_sku"] for row in data)


def test_empty_manifest_and_no_mutation_scope_are_explicit() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert manifest["products"] == []
    assert summary["exact_primary_pass_rows"] == 0
    assert summary["output"]["rows"] == 131
    assert summary["policy"] == {
        "exact_primary_source_required": True,
        "normalized_mpn_and_sku_checked": True,
        "database_mutations": 0,
        "media_mutations": 0,
        "commercial_mutations": 0,
    }
    collisions = summary["normalized_mpn_collisions"]
    assert collisions == [{"manufacturer": "Leoch", "normalized_mpn": "FT1240", "external_ids": ["bitrix:25828", "bitrix:25830"]}]
