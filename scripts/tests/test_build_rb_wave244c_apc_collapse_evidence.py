import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_wave244c_is_exact_no_repeat_and_fail_closed() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave244c-apc-collapse-evidence.py")], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"requested": 4, "ready_dry_run": 2, "held_fail_closed": 2}
    manifest = json.loads((ROOT / "docs/imports/rb-verified-noindex-duplicate-collapse-wave244c-2026-07-30.json").read_text(encoding="utf-8"))
    assert [row["duplicate_external_id"] for row in manifest["duplicates"]] == ["bitrix:23799", "bitrix:20088"]
    assert all(row["source_snapshot_sha256"] and row["source_evidence_sha256"] for row in manifest["duplicates"])
    with (ROOT / "docs/audits/generated/rb-wave244c-apc-collapse-ledger.csv").open(encoding="utf-8", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    holds = {row["duplicate_external_id"]: row for row in ledger if row["decision"] == "HOLD_FAIL_CLOSED"}
    assert set(holds) == {"bitrix:23811", "bitrix:23818"}
    assert all(row["duplicate_price"] and row["duplicate_price_evidence_count"] == "1" for row in holds.values())
    old = (ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json").read_text(encoding="utf-8")
    assert all(row["source_url"] not in old for row in ledger)
