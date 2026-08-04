import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/annotate-rb-wave244-queue.py"
OUTPUT = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.summary.json"


def test_wave244_queue_preserves_no_repeat_status_and_replaces_only_retired_duplicates() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    with OUTPUT.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    by_id = {row["product_external_id"]: row for row in rows}
    assert len(rows) == len(by_id) == summary["rows"] == 1247
    assert summary["description_present"] == 922
    assert summary["description_missing"] == 325
    assert summary["verified_image_present"] == 0
    assert len(summary["retired_verified_duplicates"]) == len(summary["replacement_rows"]) == 6
    assert not set(summary["retired_verified_duplicates"]) & set(by_id)
    assert all(
        by_id[external_id]["research_status"] == "new_after_verified_duplicate_retirement_wave244"
        for external_id in summary["replacement_rows"]
    )
    assert summary["readiness"]["eligible_site_products"] == 16805
    assert summary["readiness"]["current_content_complete_cards"] == 395
