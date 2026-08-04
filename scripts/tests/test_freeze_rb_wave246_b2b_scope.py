import csv
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.summary.json"


def test_wave246_scope_is_reproducible_unique_pending_and_partitioned():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/freeze-rb-wave246-b2b-scope.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with SCOPE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 276
    assert len({row["product_external_id"] for row in rows}) == 276
    assert Counter(row["partition"] for row in rows) == {
        "enersys": 92,
        "csb": 92,
        "delta_leoch": 92,
    }
    assert all(row["research_status"] == "pending_official_source_research" for row in rows)
    assert all(row["mpn"].strip() or row.get("model_core", "").strip() for row in rows)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["rows"] == 276
    assert summary["all_pending_before_freeze"] is True
    assert summary["all_b2b"] is True
    assert summary["database_mutations"] == 0
