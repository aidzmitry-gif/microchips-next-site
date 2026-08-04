import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave245.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-enrichment-queue-wave245.summary.json"


def test_wave245_annotation_is_reproducible_and_closes_six_replacement_rows():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/annotate-rb-wave245-queue.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with QUEUE.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["product_external_id"]: row for row in csv.DictReader(stream)}
    for external_id in ("bitrix:1569", "bitrix:1580", "bitrix:1596", "bitrix:3232"):
        assert rows[external_id]["research_status"] == "source_backed_description_applied_wave245"
        assert rows[external_id]["has_applied_description"] == "true"
    assert rows["bitrix:1598"]["research_status"] == "hold_two_exact_1c_candidates_wave245"
    assert rows["bitrix:1159"]["research_status"] == "hold_no_new_exact_primary_source_wave245"

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["rows"] == 1247
    assert summary["description_present"] == 926
    assert summary["description_missing"] == 321
    assert summary["reviewed_applied"] == 4
    assert summary["reviewed_hold"] == 2
    assert summary["membership_change"] == 0
