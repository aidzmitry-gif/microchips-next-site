import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_wave243c_is_complete_no_repeat_and_fail_closed() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave243c-remaining-description-evidence.py")], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"rows": 108, "pass": 1, "hold": 107, "exact_legacy_duplicates": 4}
    with (ROOT / "docs/audits/generated/rb-wave243c-remaining-description-ledger.csv").open(encoding="utf-8", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert len(ledger) == 108
    assert [row["external_id"] for row in ledger if row["decision"] == "PASS"] == ["bitrix:23844"]
    assert all(row["safe_to_stage"] == ("true" if row["decision"] == "PASS" else "false") for row in ledger)
    summary = json.loads((ROOT / "docs/audits/generated/rb-wave243c-remaining-description.summary.json").read_text(encoding="utf-8"))
    assert summary["scope"]["manufacturer_counts"] == {"Leoch": 50, "APC": 22, "CSB": 16, "Marathon": 8, "EnerSys": 12}
    assert summary["legacy_duplicate_count"] == 4
    identity = json.loads((ROOT / "docs/imports/rb-verified-oem-identities-wave243c-2026-07-29.json").read_text(encoding="utf-8"))
    description = json.loads((ROOT / "docs/imports/rb-source-backed-descriptions-wave243c-2026-07-29.json").read_text(encoding="utf-8"))
    assert identity["products"][0]["mpn"] == description["products"][0]["mpn"] == "RBC109"
    assert description["products"][0]["display_name"].endswith("RBC109")
