import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave243-queue.py"
OUTPUT = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave243.summary.json"


def test_wave243_queue_is_unique_refreshed_and_no_repeat_annotated() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    with OUTPUT.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    ids = {row["product_external_id"] for row in rows}
    assert len(rows) == len(ids) == summary["rows"] == 1247
    assert summary["description_present"] == 922
    assert summary["description_missing"] == 325
    assert summary["verified_image_present"] == 0
    assert not ids.intersection(summary["retired_verified_duplicates"])
    assert set(summary["replacement_rows"]) <= ids
    by_id = {row["product_external_id"]: row for row in rows}
    assert all(
        by_id[external_id]["research_status"] == "new_after_verified_duplicate_retirement"
        for external_id in summary["replacement_rows"]
    )
    assert summary["new_replacement_rows_pending_research"] == 5
