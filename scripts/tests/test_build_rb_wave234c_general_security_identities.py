from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234c-general-security-identities.py"
LEDGER = ROOT / "docs/audits/generated/rb-wave234c-general-security-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234c-general-security-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json"


def test_wave234c_general_security_is_exact_deterministic_and_commercially_inert() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    second = (hashlib.sha256(LEDGER.read_bytes()).hexdigest(), hashlib.sha256(MANIFEST.read_bytes()).hexdigest())
    assert first == second
    with LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_id = {row["external_id"]: row for row in rows}
    assert len(rows) == 37
    assert sum(row["safe_to_apply"] == "true" for row in rows) == 29
    assert by_id["bitrix:3067"]["partition"] == "hold_terminal_suffix_not_in_official_model"
    assert by_id["bitrix:3182"]["partition"] == "hold_terminal_suffix_not_in_official_model"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["products"]) == 29
    assert all(item["source_kind"] == "official_manufacturer_catalogue" for item in manifest["products"])
    assert not any(any(key in item for key in ("price", "availability", "warranty", "published")) for item in manifest["products"])
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["partition_counts"] == {"exact_safe": 29, "hold_model_absent": 2, "hold_normalized_mpn_collision": 2, "hold_terminal_suffix_not_in_official_model": 4}
    assert summary["normalized_mpn_collision_external_ids"] == ["bitrix:2721", "bitrix:2781"]
    assert summary["policy"]["commercial_mutations"] == 0
