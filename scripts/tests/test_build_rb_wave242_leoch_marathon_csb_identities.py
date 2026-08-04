from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave242-leoch-marathon-csb-identities.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave242-leoch-marathon-csb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave242-leoch-marathon-csb-identity.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave242-leoch-marathon-csb-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json"
IDENTITY_COMMAND = ROOT / "backend/app/Console/Commands/ApplyVerifiedOemIdentities.php"
DESCRIPTION_POLICY = ROOT / "backend/app/Domain/Content/DescriptionSourceEvidencePolicy.php"


def run() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)


def rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_wave242_is_complete_and_deterministic() -> None:
    run()
    before = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (LEDGER, SUMMARY, IDENTITIES, DESCRIPTIONS))
    run()
    after = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (LEDGER, SUMMARY, IDENTITIES, DESCRIPTIONS))
    assert before == after
    data = rows()
    assert len(data) == 131
    assert Counter(row["manufacturer_candidate"] for row in data) == {"Leoch": 50, "Marathon": 49, "CSB": 32}
    assert Counter(row["decision"] for row in data) == {"HOLD": 74, "PASS": 57}


def test_wave242_suffix_capacity_and_collision_guards() -> None:
    by_id = {row["external_id"]: row for row in rows()}
    assert by_id["bitrix:1726"]["decision"] == "PASS"
    assert by_id["bitrix:1726"]["suffix_check"] == "documented UL 94-V0 variant"
    assert by_id["bitrix:2777"]["terminal_check"] == "F2 documented in model table"
    assert by_id["bitrix:1418"]["partition"] == "hold_exact_suffix_not_proven"
    assert by_id["bitrix:1796"]["partition"] == "hold_exact_suffix_not_proven"
    assert by_id["bitrix:2827"]["partition"] == "hold_v0_suffix_not_proven_by_exact_source"
    assert by_id["bitrix:25828"]["partition"] == "hold_normalized_mpn_collision"
    assert by_id["bitrix:25830"]["partition"] == "hold_normalized_mpn_collision"
    assert all(row["decision"] == "HOLD" for row in rows() if row["manufacturer_candidate"] == "Leoch")


def test_manifests_contain_only_strict_pass_rows() -> None:
    data = rows()
    passed = {row["external_id"] for row in data if row["decision"] == "PASS"}
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert {row["external_id"] for row in identities} == passed
    assert {row["external_id"] for row in descriptions} == passed
    assert len(identities) == len(descriptions) == 57
    assert all(row["source_tier"] == "manufacturer_primary" for row in descriptions)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["decision_counts"] == {"HOLD": 74, "PASS": 57}
    assert summary["policy"]["database_mutations"] == 0


def php_allowed_fields(path: Path, marker: str) -> set[str]:
    source = path.read_text(encoding="utf-8")
    section = source[source.index(marker):]
    match = re.search(r"\$allowed\s*=\s*\[(.*?)\];", section, re.S)
    assert match is not None
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_manifests_match_actual_laravel_field_allowlists() -> None:
    identity_allowed = php_allowed_fields(IDENTITY_COMMAND, "private function manifest")
    description_allowed = php_allowed_fields(DESCRIPTION_POLICY, "private static function manufacturerPrimaryEvidence")
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert all(set(row) <= identity_allowed for row in identities)
    assert all("evidence_scope" not in row for row in identities)
    assert all(set(row) <= description_allowed for row in descriptions)
    assert all(row["identity_scope"] == "exact" and row["evidence_scope"] == "exact_model" for row in descriptions)
    assert all("source_snapshot_path" not in row and "source_snapshot_sha256" not in row for row in descriptions)
