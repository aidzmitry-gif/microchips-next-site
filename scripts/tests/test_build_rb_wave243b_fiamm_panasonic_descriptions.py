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
SCRIPT = ROOT / "scripts/build-rb-wave243b-fiamm-panasonic-descriptions.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave243b-fiamm-panasonic-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave243b-fiamm-panasonic-2026-07-29.json"
IDENTITY_COMMAND = ROOT / "backend/app/Console/Commands/ApplyVerifiedOemIdentities.php"
DESCRIPTION_POLICY = ROOT / "backend/app/Domain/Content/DescriptionSourceEvidencePolicy.php"


def run() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)


def rows() -> list[dict[str, str]]:
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def php_allowed_fields(path: Path, marker: str) -> set[str]:
    source = path.read_text(encoding="utf-8")
    section = source[source.index(marker):]
    match = re.search(r"\$allowed\s*=\s*\[(.*?)\];", section, re.S)
    assert match is not None
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_wave243b_is_complete_and_deterministic() -> None:
    run()
    paths = (LEDGER, SUMMARY, IDENTITIES, DESCRIPTIONS)
    before = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in paths)
    run()
    after = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in paths)
    assert before == after
    data = rows()
    assert len(data) == 88
    assert Counter(row["manufacturer_candidate"] for row in data) == {"Fiamm": 56, "Panasonic": 32}
    assert Counter(row["decision"] for row in data) == {"HOLD": 75, "PASS": 13}


def test_duplicate_gate_precedes_evidence_and_near_match_stays_distinct() -> None:
    by_model = {row["mpn_candidate"]: row for row in rows()}
    assert {
        model for model, row in by_model.items()
        if row["partition"] == "hold_legacy_canonical_duplicate"
    } == {"12FGH36", "4SLA150", "FG21202", "FG21803"}
    assert by_model["12FGH36"]["legacy_duplicate_external_ids"] == "ФР-00002108"
    assert by_model["FG21803"]["source_url"] == ""
    assert by_model["LC-R127R2PG"]["decision"] == "PASS"
    assert by_model["LC-R121R3PG"]["decision"] == "HOLD"


def test_only_exact_new_manufacturer_primary_evidence_is_staged() -> None:
    passed = {row["external_id"] for row in rows() if row["decision"] == "PASS"}
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert {row["external_id"] for row in identities} == passed
    assert {row["external_id"] for row in descriptions} == passed
    assert len(identities) == len(descriptions) == 13
    assert all(row["source_url"].startswith(("https://www.fiamm.co/", "https://api.pim.na.industrial.panasonic.com/")) for row in identities)
    assert all(row["source_tier"] == "manufacturer_primary" for row in descriptions)
    assert all(row["identity_scope"] == "exact" and row["evidence_scope"] == "exact_model" for row in descriptions)
    assert all(row["display_name"].endswith(row["mpn"]) for row in descriptions)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["source_policy"] == {
        "new_urls": 7,
        "new_sha256": 7,
        "prior_snapshot_hash_collisions": 0,
        "manufacturer_primary_only": True,
    }


def test_manifests_match_actual_laravel_field_allowlists() -> None:
    identity_allowed = php_allowed_fields(IDENTITY_COMMAND, "private function manifest")
    description_allowed = php_allowed_fields(DESCRIPTION_POLICY, "private static function manufacturerPrimaryEvidence")
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))["products"]
    assert all(set(row) <= identity_allowed for row in identities)
    assert all("evidence_scope" not in row for row in identities)
    assert all(set(row) <= description_allowed for row in descriptions)
    assert all("source_snapshot_path" not in row and "source_snapshot_sha256" not in row for row in descriptions)
